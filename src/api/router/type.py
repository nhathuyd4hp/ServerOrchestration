import os
import tempfile

import httpx
import pandas as pd
from fastapi import APIRouter

from src.api.common.response import SuccessResponse
from src.core.config import settings

router = APIRouter()

router = APIRouter(prefix="/type", tags=["Input Typing"])


@router.get("/seikyu-online")
async def seikyu_online():
    try:
        # Get Access Token
        response = httpx.post(
            url=f"https://login.microsoftonline.com/{settings.API_SHAREPOINT_TENANT_ID}/oauth2/v2.0/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "client_id": settings.API_SHAREPOINT_CLIENT_ID,
                "client_secret": settings.API_SHAREPOINT_CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        # --- #
        access_token: str = response.json().get("access_token")
        headers = {"Authorization": access_token}
        site_id = "nskkogyo.sharepoint.com,fcec6ca2-58f4-4488-abf8-34e8ffbb741d,3136a8b2-a506-44d2-ad49-324bd156147c"
        breadcrumb = "◆請求書　ベトナム専用◆/≪ベトナム≫阪和興業　新(9日(10日分)、14日(15日分)、19日(20日分)、29日(末日分)に完成).xlsm"  # noqa
        # --- #
        item_metadata = httpx.get(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{breadcrumb}",
            headers=headers,
        ).json()
        drive_id = item_metadata["parentReference"]["driveId"]
        item_id = item_metadata["id"]
        with (
            httpx.stream(
                "GET",
                f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content",
                headers=headers,
                follow_redirects=True,
            ) as response,
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            file_path: str = os.path.join(temp_dir, os.path.basename(breadcrumb))
            with open(file_path, "wb") as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    f.write(chunk)
            with pd.ExcelFile(file_path) as xls:
                sheets: list[str] = xls.sheet_names
                return SuccessResponse(
                    data=f"typing.Literal{sheets}",
                )
    except Exception:
        sheets = []
        return SuccessResponse(
            data=f"typing.Literal{sheets}",
        )
