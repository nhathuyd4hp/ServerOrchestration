from celery import signals
from celery.apps.worker import Worker
from sqlmodel import Session, select

import redis
from src.core.config import settings
from src.model import Runs
from src.model.runs import Status


@signals.worker_init.connect
def setup_worker_resources(sender: Worker, **kwargs):
    redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
        db=settings.REDIS_DB,
        decode_responses=True,
    ).flushdb()


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, **kwargs):
    with Session(settings.db_engine) as session:
        statement = select(Runs).where(Runs.id == task_id)
        record = session.exec(statement).one_or_none()
        if record:
            return
        session.add(
            Runs(
                id=task_id,
                robot=sender.name,
                parameters=kwargs.get("kwargs") if kwargs.get("kwargs") else None,
            )
        )
        session.commit()


@signals.task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    with Session(settings.db_engine) as session:
        statement = select(Runs).where(Runs.id == sender.request.id)
        record = session.exec(statement).one_or_none()
        if not record:
            return
        record.status = Status.SUCCESS
        record.result = result
        session.add(record)
        session.commit()


@signals.task_failure.connect
def task_failure_handler(sender=None, exception=None, **kwargs):
    with Session(settings.db_engine) as session:
        statement = select(Runs).where(Runs.id == sender.request.id)
        record = session.exec(statement).one_or_none()
        if not record:
            return
        record.status = Status.FAILURE
        record.result = str(exception)
        session.add(record)
        session.commit()
