from apscheduler.job import Job
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from src.api.common.response import SuccessResponse
from src.api.dependency import get_scheduler, get_session
from src.schema.run import RunSchedule
from src.service import ScheduleService
from src.worker import Worker

router = APIRouter(prefix="/schedule", tags=["Schedule"])


@router.get(
    path="",
    name="Danh sách chạy",
    response_model=SuccessResponse,
)
def get_schedules(scheduler: BackgroundScheduler = Depends(get_scheduler)):
    jobs: list[Job] = scheduler.get_jobs()
    jobs = [
        {
            "id": job.id,
            "name": job.args[0],
            "parameters": job.kwargs,
            "next_run_time": job.next_run_time,
            "start_date": job.trigger.start_date,
            "end_date": job.trigger.end_date,
            "status": "ACTIVE" if job.next_run_time else "EXPIRED",
        }
        for job in jobs
    ]
    return SuccessResponse(data=jobs)


@router.post(
    path="",
    name="Lập lịch chạy",
    status_code=201,
    response_model=SuccessResponse,
)
def set_robot_schedule(
    data: RunSchedule,
    scheduler: BackgroundScheduler = Depends(get_scheduler),
    session: Session = Depends(get_session),
):
    if data.name not in Worker.tasks.keys():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    schedule = ScheduleService(session).create(data)
    job: Job = scheduler.add_job(
        id=schedule.id,
        func=Worker.send_task,
        args=(data.name,),
        trigger=CronTrigger(
            hour=data.schedule.hour,
            minute=data.schedule.minute,
            day_of_week=data.schedule.day_of_week,
            start_date=data.schedule.start_date,
            end_date=data.schedule.end_date,
        ),
    )
    return SuccessResponse(
        data={
            "id": job.id,
            "name": job.name,
            "args": job.args,
            "kwargs": job.kwargs,
            "next_run_time": job.next_run_time,
        }
    )


@router.delete(
    path="/{id}",
    name="Xóa lịch chạy",
    response_model=SuccessResponse,
)
def delete_robot_schedule(
    id: str,
    scheduler: BackgroundScheduler = Depends(get_scheduler),
    session: Session = Depends(get_session),
):
    schedule = ScheduleService(session).deleteByID(id)
    scheduler.remove_job(id)
    return SuccessResponse(data=schedule)
