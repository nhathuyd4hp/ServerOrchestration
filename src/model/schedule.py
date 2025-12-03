from datetime import datetime

from sqlmodel import Field

from src.model.base import Base


class Schedule(Base, table=True):
    robot: str = Field(nullable=False)
    parameters: str | None = Field(default=None)
    hour: int | None = Field(default=None)
    minute: int | None = Field(default=None)
    day_of_week: str | None = Field(default=None)
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)
