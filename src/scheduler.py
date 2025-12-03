from apscheduler import events
from apscheduler.events import JobEvent
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session

from src.core.config import settings
from src.model import Runs
from src.model.runs import Status


def listener(event: JobEvent):
    run = Runs(
        robot=scheduler.get_job(event.job_id).args[0],
        parameters=scheduler.get_job(event.job_id).kwargs if scheduler.get_job(event.job_id).kwargs else None,
    )
    # ---- #
    if event.code == events.EVENT_JOB_REMOVED:
        run.status = Status.CANCEL
    if event.code == events.EVENT_JOB_ERROR:
        run.status = Status.FAILURE
    with Session(settings.db_engine) as session:
        session.add(run)
        session.commit()


scheduler = BackgroundScheduler(timezone="Asia/Ho_Chi_Minh")

scheduler.add_listener(listener, events.EVENT_EXECUTOR_REMOVED | events.EVENT_JOB_ERROR)
