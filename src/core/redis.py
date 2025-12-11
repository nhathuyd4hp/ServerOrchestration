import redis
from src.core.config import settings
from enum import Enum

class Channel(str,Enum):
    RELOAD = "RELOAD"
redisClient = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_HOST,
    db=settings.REDIS_DB,
)
    