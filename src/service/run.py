import json
from typing import Dict, List

from fastapi import HTTPException, status
from sqlmodel import Session, select

from src.model import Runs
from src.model.runs import Status
from src.schema.run import RunManual


class RunService:
    def __init__(self, session: Session):
        self.session = session

    def findByID(self, id: str) -> Runs | None:
        return self.session.exec(select(Runs).where(Runs.id == id)).first()

    def findByStatus(self, status: Status) -> List[Runs]:
        return self.session.exec(select(Runs).where(Runs.status == status)).all()

    def findMany(self) -> List[Runs]:
        return self.session.exec(select(Runs)).all()

    def create(self, data: Dict | RunManual) -> Runs:
        if not isinstance(data, (dict, RunManual)):
            raise HTTPException(status_code=status, detail="invalid data")
        history = (
            Runs(
                robot=data.name,
                parameters=json.dumps(data.parameters) if data.parameters else None,
            )
            if isinstance(data, RunManual)
            else Runs(**data)
        )
        self.session.add(history)
        self.session.commit()
        self.session.refresh(history)
        return history
