import io
import re
import tempfile
from datetime import datetime

import pandas as pd
import redis
from celery import shared_task
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.DrawingClassic.automation import AndPad, SharePoint, WebAccess
from src.service import ResultService as minio


@shared_task(
    bind=True,
    name="Gửi tin nhắn xác nhận Classic",
)
def gui_ban_ve_xac_nhan_classic(self):
    logger = Log.get_logger(channel=self.request.id, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    with (
        sync_playwright() as p,
        tempfile.TemporaryDirectory() as temp_dir,
    ):
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        with (
            WebAccess(
                username=settings.WEBACCESS_USERNAME,
                password=settings.WEBACCESS_PASSWORD,
                playwright=p,
                browser=browser,
                context=context,
            ) as wa,
            SharePoint(
                domain=settings.SHAREPOINT_DOMAIN,
                username=settings.SHAREPOINT_EMAIL,
                password=settings.SHAREPOINT_PASSWORD,
                playwright=p,
                browser=browser,
                context=context,
            ) as sp,
            AndPad(
                domain="https://work.andpad.jp/",
                username="clasishome@nsk-cad.com",
                password="nsk159753",
                playwright=p,
                browser=browser,
                context=context,
            ) as ap,
        ):
            logger.info("WebAccess - download data")
            orders = wa.download_data(building="クラシスホーム")
            orders = orders[orders["確未"] == "未"]
            orders = orders[["案件番号", "得意先名", "物件名", "確定納期", "担当2", "資料リンク"]]
            logger.info(orders.shape)
            orders["Result"] = pd.NA
            # ---- #
            for index, row in orders.iterrows():
                _, _, 物件名, 確定納期, 担当2, 資料リンク, _ = row
                logger.info(f"{物件名} - {確定納期} - {担当2} - {資料リンク}")
                if pd.isna(物件名):
                    logger.warning("物件名 is null")
                    continue
                if pd.isna(資料リンク):
                    logger.warning("資料リンク is null")
                    continue
                if pd.isna(確定納期):
                    logger.warning("確定納期 is null")
                    continue
                if pd.isna(担当2):
                    logger.warning("担当2 is null")
                    continue
                logger.info("Download PDF")
                downloads = sp.download_files(
                    url=資料リンク,
                    file=re.compile(r".*\.pdf$", re.IGNORECASE),
                    steps=[
                        re.compile("^割付図・エクセル$"),
                    ],
                    save_to=temp_dir,
                )
                if len(downloads) != 1:
                    logger.warning(f"{len(downloads)} PDF")
                    orders.at[index, "Result"] = f"{len(downloads)} file PDF"
                    continue
                logger.info("Send message")
                orders.at[index, "Result"] = ap.send_message(
                    object_name=物件名,
                    message=f"""いつもお世話になっております。
現場：{物件名}
{"/".join(確定納期.split("/")[1:])} 倉庫入れ予定です。
上記の現場、まだ図面承認されていませんので、
お手数をおかけしますが、至急ご確認お願い致します。
よろしくお願いいたします。
""",
                    tags=["配送管理･追加発注(大前)", "林(拓) [資材課]", 担当2],
                    attachments=downloads[0],
                )
            # --- Upload to Minio
            # 1. Khởi tạo buffer dạng BytesIO (vì Excel là binary)
            excel_buffer = io.BytesIO()

            # 2. Ghi dataframe vào buffer dưới dạng Excel
            # Lưu ý: Cần cài thư viện openpyxl (pip install openpyxl)
            orders.to_excel(excel_buffer, index=False, engine="openpyxl")

            # 3. Đưa con trỏ về đầu file để chuẩn bị đọc
            excel_buffer.seek(0)

            result = minio.put_object(
                bucket_name=settings.MINIO_BUCKET,
                # SỬA Ở ĐÂY: đổi đuôi file thành .xlsx
                object_name=f"DrawingClassic/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx",
                data=excel_buffer,
                length=excel_buffer.getbuffer().nbytes,
                # SỬA Ở ĐÂY: đổi content_type sang định dạng Excel
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

            return result.object_name
