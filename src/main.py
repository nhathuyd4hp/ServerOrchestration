import asyncio
from contextlib import asynccontextmanager, suppress

from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

import redis.asyncio as redis
from src.api.common.response import SuccessResponse
from src.api.middleware import GlobalExceptionMiddleware
from src.api.router import api
from src.core.config import settings
from src.core.redis import Async_Redis_POOL
from src.scheduler import scheduler
from src.service import ResultService, ScheduleService
from src.socket import manager
from src.worker import Worker


async def subscriber(*args):
    r = redis.Redis(connection_pool=Async_Redis_POOL)
    p = r.pubsub()
    await p.subscribe(*args)
    async for message in p.listen():
        if message["type"] != 'message':
            continue
        channel: str = message['channel'].decode("utf-8")
        raw = message['data']
        if isinstance(raw, bytes):
            data = raw.decode("utf-8")
        else:
            data = str(raw)
        if channel == "CELERY":
            await manager.broadcast(data)
        else:
            await manager.broadcast(data,channel)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(subscriber("CELERY","LOG"))
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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api, prefix=settings.ROOT_PATH)


@app.websocket("/ws")
async def websocket_global(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/channel/{channel}")
async def websocket_channel(websocket: WebSocket, channel: str | None = None):
    await manager.connect(websocket, channel)
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
