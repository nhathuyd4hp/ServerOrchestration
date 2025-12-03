from fastapi import Request
from sqlmodel import Session

from src.core.config import settings


def get_session():
    with Session(settings.db_engine) as session:
        yield session


def get_scheduler(request: Request):
    return request.app.state.scheduler
