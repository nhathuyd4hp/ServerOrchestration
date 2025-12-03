from typing import Dict, List

from fastapi import HTTPException, status
from sqlmodel import Session, select

from src.model import Schedule
from src.schema.run import RunSchedule


class ScheduleService:
    def __init__(self, session: Session):
        self.session = session

    def findMany(self) -> List[Schedule]:
        return self.session.exec(select(Schedule)).all()

    def create(self, data: Dict | RunSchedule) -> Schedule:
        if not isinstance(data, (dict, RunSchedule)):
            raise HTTPException(status_code=status, detail="invalid data")
        schedule = (
            Schedule(
                robot=data.name,
                parameters=data.parameters,
                hour=data.schedule.hour,
                minute=data.schedule.minute,
                day_of_week=data.schedule.day_of_week,
                start_date=data.schedule.start_date,
                end_date=data.schedule.end_date,
            )
            if isinstance(data, RunSchedule)
            else Schedule(**data)
        )
        self.session.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        return schedule

    def deleteByID(self, id: str) -> Schedule:
        statement = select(Schedule).where(Schedule.id == id)
        schedule = self.session.exec(statement).one_or_none()
        if schedule is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="schedule not found")
        self.session.delete(schedule)
        self.session.commit()
        return schedule
