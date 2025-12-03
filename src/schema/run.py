from datetime import date
from typing import Optional

from pydantic import BaseModel


class RunManual(BaseModel):
    name: str
    parameters: dict | None = None


class ScheduleInput(BaseModel):
    # Cron expression fields
    hour: int | None = None
    minute: int | None = None
    day_of_week: str | None = None
    # Schedule control
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class RunSchedule(BaseModel):
    name: str
    schedule: ScheduleInput
    parameters: dict | None = None
