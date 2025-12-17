from enum import StrEnum
from typing import TYPE_CHECKING

from sqlmodel import Column, Field, Relationship, Text

from src.model.base import Base

if TYPE_CHECKING:
    from src.model.log import Log


class Status(StrEnum):
    CANCEL = "CANCEL"
    WAITING = "WAITING"
    PENDING = "PENDING"
    FAILURE = "FAILURE"
    SUCCESS = "SUCCESS"


class Runs(Base, table=True):
    robot: str = Field(nullable=False)
    parameters: str | None = Field(default=None)
    status: Status = Field(default=Status.WAITING)
    result: str | None = Field(sa_column=Column(Text))

    logs: list["Log"] = Relationship(back_populates="run")
