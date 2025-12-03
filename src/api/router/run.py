import os
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from src.api.common.response import SuccessResponse
from src.api.dependency import get_session
from src.core.config import settings
from src.model.runs import Status
from src.service import ResultService, RunService

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get(
    path="",
    name="Lịch sử chạy",
    response_model=SuccessResponse,
)
def get_histories(
    session: Session = Depends(get_session),
    status: Status | None = Query(default=None),
):
    if status:
        histories = RunService(session).findByStatus(status)
    else:
        histories = RunService(session).findMany()
    return SuccessResponse(data=histories)


@router.get(path="/result/{id}", name="Lấy kết quả chạy")
def get_result(id: str, session: Session = Depends(get_session)):
    history = RunService(session).findByID(id)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    if history.status != Status.SUCCESS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="run not successful")
    response = ResultService.get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=history.result,
    )
    data = BytesIO(response.read())
    response.close()
    response.release_conn()
    return StreamingResponse(
        data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{os.path.basename(history.result)}"'},
    )
