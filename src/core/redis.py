from enum import Enum

import redis
from src.core.config import settings


class Channel(str, Enum):
    RELOAD = "RELOAD"


redisClient = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_HOST,
    db=settings.REDIS_DB,
)
