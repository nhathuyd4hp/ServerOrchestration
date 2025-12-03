from enum import StrEnum

from sqlmodel import Column, Field, Text

from src.model.base import Base


class Status(StrEnum):
    CANCEL = "CANCEL"
    PENDING = "PENDING"
    FAILURE = "FAILURE"
    SUCCESS = "SUCCESS"


class Runs(Base, table=True):
    robot: str = Field(nullable=False)
    parameters: str | None = Field(default=None)
    status: Status = Field(default=Status.PENDING)
    result: str | None = Field(sa_column=Column(Text))
