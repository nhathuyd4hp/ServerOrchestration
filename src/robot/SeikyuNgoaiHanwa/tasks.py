import tempfile
from src.core.config import settings
from src.robot.SeikyuNgoaiHanwa.api import APISharePoint
from datetime import datetime
from celery import shared_task

@shared_task(
    bind=True,
    name="Seikyu Ngoài Hanwa"
)
def seikyu(
    self,
    from_date: datetime | str,
    to_date: datetime | str,
):
    with (
        tempfile.TemporaryDirectory() as temp_dir
    ):
        SeikyuFile= APISharePoint(
            TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
            CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
            CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
        ).download_item(
            site_id="nskkogyo.sharepoint.com,fcec6ca2-58f4-4488-abf8-34e8ffbb741d,3136a8b2-a506-44d2-ad49-324bd156147c",
            breadcrumb="◆請求書　ベトナム専用◆/≪ベトナム≫請求書　阪和以外　(9日AM(10日分)、14日AM(15日分)、19日AM(20日分)、29日AM(末日分)に完成).xlsm",
            save_to=temp_dir
        )
        if SeikyuFile is None:
            raise FileNotFoundError("Không tìm thấy file `≪ベトナム≫請求書　阪和以外　(9日AM(10日分)、14日AM(15日分)、19日AM(20日分)、29日AM(末日分)に完成).xlsm`")
        
