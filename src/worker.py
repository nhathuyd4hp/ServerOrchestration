from celery import Celery

from src.core.config import settings
from src.robot import *  # noqa
from src.worker_signals import *  # noqa - Thêm dòng này

Worker = Celery(
    "orchestration",
    broker=settings.REDIS_CONNECTION_STRING,
    backend=settings.REDIS_CONNECTION_STRING,
)
