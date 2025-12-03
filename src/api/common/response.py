from typing import Any

from pydantic import BaseModel


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "success"
    data: Any | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    messsage: str = "error"
