import inspect

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from src.api.common.response import SuccessResponse
from src.api.dependency import get_session
from src.schema.run import RunManual
from src.service import RunService
from src.worker import Worker

router = APIRouter(prefix="/robots", tags=["Robot"])


@router.get(
    path="",
    name="Danh sách robot",
    response_model=SuccessResponse,
)
def get_robots():
    robots = []
    for name, task in Worker.tasks.items():
        if name.startswith("celery."):
            continue
        try:
            sig = inspect.signature(task)
            robots.append(
                {
                    "name": name,
                    "active": True,
                    "parameters": [
                        {
                            "name": p.name,
                            "default": p.default if p.default != inspect.Parameter.empty else None,
                            "required": p.default == inspect.Parameter.empty,
                            "annotation": "str" if p.annotation == inspect._empty else str(p.annotation),
                        }
                        for p in sig.parameters.values()
                    ],
                }
            )
        except Exception:
            robots.append(
                {
                    "name": name,
                    "active": False,
                    "parameters": [
                        {
                            "name": p.name,
                            "default": p.default if p.default != inspect.Parameter.empty else None,
                            "required": p.default == inspect.Parameter.empty,
                            "annotation": "str" if p.annotation == inspect._empty else str(p.annotation),
                        }
                        for p in sig.parameters.values()
                    ],
                }
            )
    return SuccessResponse(data=robots)


@router.post(
    path="/run",
    name="Chạy thủ công",
    response_model=SuccessResponse,
)
async def run_robot_manual(
    data: RunManual,
    session: Session = Depends(get_session),
):
    if data.name not in Worker.tasks.keys():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    run = RunService(session).create(data)
    Worker.send_task(
        name=data.name,
        kwargs=data.parameters,
        task_id=run.id,
    )
    return SuccessResponse(data=run)
