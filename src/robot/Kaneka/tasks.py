import os
import tempfile
import time
from enum import StrEnum
from urllib.parse import urljoin

import redis
from celery import shared_task
from selenium import webdriver

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.Kaneka.common.decorator import error_handling
from src.robot.Kaneka.service import GoogleSheet, MailDealer, SharePoint


class ColorMapping(StrEnum):
    YELLOW = "#ffff00"
    WHITE = "#ffffff"
    BLUE = "#00ffff"
    GRAY = "#999999"
    GREEN = "#6aa84f"


class SheetMapping(StrEnum):
    KENTEC_1_T1_T6 = "976467386"
    KENTEC_2_T1_T6 = "1303713830"
    パネル_T1_T6 = "1709675894"

    def __str__(self):
        return self.value


@shared_task(bind=True, name="Kaneka")
@error_handling()
def main(self):
    with tempfile.TemporaryDirectory() as temp_dir:
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-notifications")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-session-crashed-bubble")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": temp_dir,
                "download.prompt_for_download": False,
                "safebrowsing.enabled": True,
            },
        )
        APPLICATION_SCRIPTS_URL: str = (
            "https://script.google.com/macros/s/AKfycbwUY_GGn7fsoQCr9Ouq9vz2DIADaEf-hNYtUcwRTM0xNYsJhE_b3HbYFisWnA_CRMDI/exec"
        )
        # --- Common --- #
        logger = Log.get_logger(channel=self.request.id, redis_client=redis.Redis(connection_pool=REDIS_POOL))
        # --- Services --- #
        MD = MailDealer(
            username=settings.MAIL_DEALER_USERNAME,
            password=settings.MAIL_DEALER_PASSWORD,
            options=options,
            log_name="MailDealer",
        )
        SP = SharePoint(
            url=settings.SHAREPOINT_DOMAIN,
            username=settings.SHAREPOINT_EMAIL,
            password=settings.SHAREPOINT_PASSWORD,
            options=options,
            log_name="SharePoint",
        )
        GS = GoogleSheet(application_scripts_url=APPLICATION_SCRIPTS_URL, log_name="GoogleSheet")
        mails: list[dict] = []
        for sid in SheetMapping:
            _, sheet = GS.getSheet(sid)
            sheet.index = sheet.index + 2
            sheet = sheet[sheet["ID MAIL"] != ""]
            MAIL_IDS = sheet["ID MAIL"].unique()
            for ID in MAIL_IDS:
                sheet_based_on_id = sheet[sheet["ID MAIL"] == ID]
                backgrounds: list[list[str]] = sheet_based_on_id["background"].to_list()
                if all(background[0] == ColorMapping.BLUE.value for background in backgrounds):
                    mails.append(
                        {
                            "mail_id": ID,
                            "sheet_id": sid.value,
                            "sheet_name": sid.name,
                            "row": sheet_based_on_id.index.to_list(),
                            "type": 1,
                        }
                    )
                if all(background[0] == ColorMapping.GREEN.value for background in backgrounds):
                    mails.append(
                        {
                            "mail_id": ID,
                            "sheet_id": sid.value,
                            "sheet_name": sid.name,
                            "row": sheet_based_on_id.index.to_list(),
                            "type": 2,
                        }
                    )
        data = []
        if not mails:
            logger.info("Danh sách mail cần trả lời rỗng")
            return
        for mail in mails:
            if mail.get("mail_id").count("-") != 1:
                continue
            logger.info(f"Mail: {mail}")
            if mail["type"] == 1:
                if mail.get("sheet_name") == "KENTEC_1_T1_T6":
                    success, note = MD.reply(
                        mail_id=mail.get("mail_id"),
                        reply_to="全員に返信",
                        signature="署名なし",
                        templates=["kaneka", "KKT Box"],
                    )
                    data.append({**mail, "result": success, "note": note})
                    if success:
                        for index in mail.get("row"):
                            GS.setColor(
                                sheet_id=mail.get("sheet_id"),
                                row=index,
                                color=ColorMapping.GRAY,
                            )

                else:
                    success, note = MD.reply(
                        mail_id=mail.get("mail_id"),
                        reply_to="全員に返信",
                        signature="署名なし",
                        templates=["kaneka", "KFP Box"],
                    )
                    data.append({**mail, "result": success, "note": note})
                    if success:
                        for index in mail.get("row"):
                            GS.setColor(
                                sheet_id=mail.get("sheet_id"),
                                row=index,
                                color=ColorMapping.GRAY,
                            )
            if mail["type"] == 2 and mail.get("sheet_name") != "KENTEC_1_T1_T6":
                mail_id: str = mail.get("mail_id")
                url, searchData = SP.search(
                    site_url=urljoin(settings.SHAREPOINT_DOMAIN, "/sites/2021/Shared Documents/は行/KANEKA JOB"),
                    keyword=mail_id.split("-")[0],
                )
                if not url or searchData.empty:
                    continue
                has_pdf = any(fp.lower().endswith((".pdf", ".PDF")) for fp in searchData["Name"].to_list())
                has_excel = any(fp.lower().endswith((".xlsm", ".xlsx")) for fp in searchData["Name"].to_list())
                if not (has_pdf and has_excel):
                    continue
                for _ in range(5):
                    if download_files := SP.download(
                        site_url=url,
                        file_pattern=".*.(pdf|xlsm|xlsx|PDF|xls)$",
                    ):
                        has_pdf = any(fp.lower().endswith((".pdf", ".PDF")) for fp, _ in download_files)
                        has_excel = any(fp.lower().endswith((".xlsm", ".xlsx")) for fp, _ in download_files)
                        if not (has_pdf and has_excel):
                            for fp, _ in download_files:
                                os.remove(fp)
                                time.sleep(1)
                            continue
                        download_files = [download_file[0] for download_file in download_files]
                        success, note = MD.reply(
                            mail_id=mail.get("mail_id"),
                            reply_to="全員に返信",
                            signature="署名なし",
                            templates=["kaneka", "KFP file attach"],
                            attachments=download_files,
                        )
                        data.append({**mail, "result": success, "note": note})
                        if success:
                            for index in mail.get("row"):
                                GS.setColor(
                                    sheet_id=mail.get("sheet_id"),
                                    row=index,
                                    color=ColorMapping.GRAY,
                                )
                            for file in download_files:
                                os.remove(file)
                        break
