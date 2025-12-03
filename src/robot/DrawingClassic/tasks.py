import io
import re
from datetime import datetime

import pandas as pd
from celery import shared_task
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.robot.DrawingClassic.automation import AndPad, SharePoint, WebAccess
from src.service import ResultService


@shared_task
def drawing_classic():
    with sync_playwright() as p:
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
            orders = wa.download_data(building="クラシスホーム")
            orders = orders[orders["確未"] == "未"]
            orders = orders[["案件番号", "得意先名", "物件名", "確定納期", "担当2", "資料リンク"]]
            orders["Result"] = pd.NA
            orders = orders.head(1)
            # ---- #
            for index, row in orders.iterrows():
                _, _, 物件名, 確定納期, 担当2, 資料リンク, _ = row
                if pd.isna(物件名):
                    continue
                if pd.isna(資料リンク):
                    continue
                if pd.isna(確定納期):
                    continue
                if pd.isna(担当2):
                    continue
                downloads = sp.download_files(
                    url=資料リンク,
                    file=re.compile(r".*\.pdf$", re.IGNORECASE),
                    steps=[
                        re.compile("^割付図・エクセル$"),
                    ],
                    save_to="downloads/DrawingClassic",
                )
                if len(downloads) != 1:
                    orders.at[index, "Result"] = f"Tìm thấy {len(downloads)} file bản vẽ"
                    continue
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
            csv_buffer = io.StringIO()
            orders.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            result = ResultService.put_object(
                bucket_name=settings.MINIO_BUCKET,
                object_name=f"DrawingClassic/{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.xlsx",
                data=io.BytesIO(csv_buffer.getvalue().encode("utf-8")),
                length=len(csv_buffer.getvalue()),
            )
            return result.object_name
