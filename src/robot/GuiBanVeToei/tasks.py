import io
import re
import tempfile
from datetime import datetime

import pandas as pd
from celery import shared_task
from playwright.sync_api import sync_playwright

import redis
from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.GuiBanVeToei.automation import MailDealer, SharePoint, WebAccess
from src.service import ResultService as minio


@shared_task(bind=True)
def gui_ban_ve_toei(
    self,
    from_date: datetime,
    to_date: datetime,
):
    TaskID = self.request.id
    logger = Log.get_logger(channel=TaskID, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    """
    Robot Name: Gửi bản vẽ Toei
    1. Download Data
    - Bot vào access lọc tên công trình 東栄住宅, trạng thái 作図済、CBUP済
    2.Dựa trên list bài đó tiến hành gửi bản vẽ cho từng bài:
    - Down file bản vẽ pdf từ 365
    - Tạo mail
    - Đính kèm file
    - Nhấn lưu mail
    - Chuyển trạng thái access 図面: 送付済、CB送付済

    ※Phần nội dung mail:
    From: ighd@nsk-cad.com
    To: địa chỉ mail chổ 担当者2 (メールアドレス)
    Tiêu đề: 東栄住宅　tên bài  軽天割付図送付
    Nội dung mail:
    ご担当者様

    お世話になっております。
    表題の軽天図送付致します。
    nouki納品
    よろしくお願いいたします。


    *エヌ・エス・ケー工業　SDGｓ宣言
    ***************************************
    エヌエスケー工業㈱
    TEL:06-4808-4081
    FAX:06-4808-4082
    営業時間：9:00～18:00
    休日:日曜・祝日

    https://www.nsk-cad.com/
    ***************************************
    """
    logger.info(f"Chạy với tham số: {from_date} - {to_date}")
    with tempfile.TemporaryDirectory() as temp_dir:
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
                MailDealer(
                    username=settings.MAIL_DEALER_USERNAME,
                    password=settings.MAIL_DEALER_PASSWORD,
                    playwright=p,
                    browser=browser,
                    context=context,
                ) as md,
            ):
                logger.info("Tải dữ liệu từ WebAccess")
                data = wa.download_data(
                    from_date=datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y/%m/%d"),
                    to_date=datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S.%f").strftime("%Y/%m/%d"),
                )
                data = data[["案件番号", "得意先名", "物件名", "図面", "確定納期", "資料リンク"]].copy()
                data["Result"] = pd.NA
                for index, row in data.iterrows():
                    # Kiểm tra nouki
                    if pd.isna(row["確定納期"]):
                        data.at[index, "Result"] = "Không có nouki"
                        continue
                    # Kiểm tra địa chỉ gửi
                    mail_address = wa.mail_address(str(row["案件番号"]))
                    if mail_address is None:
                        data.at[index, 'Result'] = "Không tìm thấy mail nhận"
                        continue
                    downloads = sp.download(
                        url=row["資料リンク"],
                        steps=[
                            re.compile("^割付図・エクセル$"),
                        ],
                        file=re.compile(r"\.pdf$", re.IGNORECASE),
                        save_to=temp_dir,
                    )
                    if len(downloads) == 0:
                        data.at[index, "Result"] = "Không tìm thấy bản vẽ"
                        continue
                    if len(downloads) != 1:
                        data.at[index, "Result"] = f"Có {len(downloads)} file bản vẽ"
                        continue
                    logger.info("Gửi mail")
                    if not md.send_mail(
                        to=mail_address,
                        subject=f"東栄住宅 {row['物件名']} 軽天割付図送付",
                        nouki=row["確定納期"],
                        file=downloads[0],
                    ):
                        data.at[index, "Result"] = "Gửi mail thất bại"
                        continue
                    if not wa.update_state(case=str(row["案件番号"]), current_state=str(row["図面"])):
                        data.at[index, "Result"] = "Đã gửi mail | Cập nhật WebAccess lỗi"
                        continue
                    data.at[index, "Result"] = "Thành công"
                logger.info("Lưu file kết quả")
                # Upload to S3
                excel_buffer = io.BytesIO()
                data.to_excel(excel_buffer, index=False, engine="xlsxwriter")
                excel_buffer.seek(0)
                result = minio.put_object(
                    bucket_name=settings.MINIO_BUCKET,
                    object_name=f"GuiBanVeToei/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx",
                    data=excel_buffer,
                    length=excel_buffer.getbuffer().nbytes,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                return result.object_name
    logger.info("Hoàn thành")
