from datetime import datetime
from uuid import uuid4

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class Base(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        sa_column_kwargs={"default": func.now(), "onupdate": func.now()},
    )
