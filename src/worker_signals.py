import redis
from celery import signals
from sqlmodel import Session, select

from src.core.config import settings
from src.core.redis import REDIS_POOL
from src.model import Runs
from src.model.runs import Status


@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, **kwargs):
    with Session(settings.db_engine) as session:
        statement = select(Runs).where(Runs.id == task_id)
        record: Runs = session.exec(statement).one_or_none()
        if record:
            record.status = Status.PENDING
            session.add(record)
        else:
            session.add(
                Runs(
                    id=task_id,
                    robot=sender.name,
                    parameters=kwargs.get("kwargs") if kwargs.get("kwargs") else None,
                )
            )
        session.commit()
        redis.Redis(connection_pool=REDIS_POOL).publish(
            "CELERY", f"{sender.name.split(".")[-1].replace("_"," ").title()} bắt đầu"
        )


@signals.task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    with Session(settings.db_engine) as session:
        statement = select(Runs).where(Runs.id == sender.request.id)
        record: Runs = session.exec(statement).one_or_none()
        if not record:
            return
        record.status = Status.SUCCESS
        record.result = str(result)
        session.add(record)
        session.commit()
        redis.Redis(connection_pool=REDIS_POOL).publish(
            "CELERY", f"{record.robot.split(".")[-1].replace("_"," ").title()} hoàn thành"
        )


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
        redis.Redis(connection_pool=REDIS_POOL).publish(
            "CELERY", f"{record.robot.split(".")[-1].replace("_"," ").title()} có lỗi"
        )
