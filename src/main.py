import asyncio
from contextlib import asynccontextmanager, suppress

import redis.asyncio as redis
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from src.api.common.response import SuccessResponse
from src.api.middleware import GlobalExceptionMiddleware
from src.api.router import api
from src.core.config import settings
from src.scheduler import scheduler
from src.service import ResultService, ScheduleService
from src.socket import manager
from src.worker import Worker


async def subscriber():
    r = redis.Redis(host="192.168.0.146", port=6379, db=0)
    p = r.pubsub()
    await p.subscribe("CELERY")
    async for message in p.listen():
        await manager.broadcast(message["data"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(subscriber())
    # --- Scheduler --- #
    with Session(settings.db_engine) as session:
        schedules = ScheduleService(session).findMany()
        for schedule in schedules:
            with suppress(Exception):
                scheduler.add_job(
                    id=schedule.id,
                    func=Worker.send_task,
                    args=(schedule.robot,),
                    trigger=CronTrigger(
                        hour=schedule.hour,
                        minute=schedule.minute,
                        day_of_week=schedule.day_of_week,
                        start_date=schedule.start_date,
                        end_date=schedule.end_date,
                    ),
                )
    scheduler.start()
    app.state.scheduler = scheduler
    # --- MinIO --- #
    if not ResultService.bucket_exists(settings.MINIO_BUCKET):
        ResultService.make_bucket(settings.MINIO_BUCKET)
    yield
    task.cancel()
    scheduler.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
)
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Cho phép cookies/headers ủy quyền
    allow_methods=["*"],  # Cho phép tất cả các phương thức HTTP (GET, POST, PUT, DELETE, v.v.)
    allow_headers=["*"],  # Cho phép tất cả các tiêu đề HTTP
)

app.include_router(api, prefix=settings.ROOT_PATH)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post(path="/broadcast", tags=["WebSocket"])
async def broadcast_message(message: str, task: BackgroundTasks):
    task.add_task(manager.broadcast, message)
    return SuccessResponse(data=message)


# Handle Exception
@app.exception_handler(HTTPException)
async def exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": str(exc.detail),
        },
    )


# Handle Undefined API
@app.api_route(
    path="/{path:path}",
    methods=["GET", "POST"],
    include_in_schema=False,
)
async def catch_all(path: str, request: Request):
    return JSONResponse(
        status_code=404,
        content={"success": False, "message": f"{request.method} {request.url.path} is undefined"},
    )
