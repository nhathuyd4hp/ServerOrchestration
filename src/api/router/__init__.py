from fastapi import APIRouter

from src.api.router.robot import router as RobotRouter
from src.api.router.run import router as RunRouter
from src.api.router.schedule import router as ScheduleRouter
from src.api.router.type import router as TypeRouter

api = APIRouter()
api.include_router(RobotRouter)
api.include_router(RunRouter)
api.include_router(ScheduleRouter)
api.include_router(TypeRouter)
