import os
import re
import shutil
import tempfile
import threading
import time
from contextlib import suppress
from datetime import datetime

import pandas as pd
import redis
import xlwings as xw
from celery import shared_task
from filelock import FileLock
from openpyxl.utils import get_column_letter
from playwright.sync_api import sync_playwright
from pywinauto import Desktop
from pywinauto.application import Application, WindowSpecification

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.Tochigi.api import APISharePoint
from src.robot.Tochigi.automation import SharePoint, WebAccess


def clean_value(v):
    import math

    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def 確認():
    while True:
        found = False
        for win in Desktop(backend="win32").windows():
            if win.window_text() == "確認":
                found = True
                break
        if found:
            break
        time.sleep(1)
    while True:
        app = Application(backend="win32").connect(title="確認")
        dialog: WindowSpecification = app.window(title="確認")
        root_window: int = dialog.handle
        dialog.wait("ready", timeout=10)
        dialog.child_window(title="&Yes", class_name="Button").click()
        still_exists = any(win.handle == root_window for win in Desktop(backend="win32").windows())
        if still_exists:
            time.sleep(1)
            continue
        else:
            break


def Fname(path: str):
    while True:
        found = False
        for win in Desktop(backend="win32").windows():
            if win.window_text() == "Browse":
                found = True
                break
        if found:
            break
        time.sleep(0.5)
    while True:
        app = Application(backend="win32").connect(title_re="Browse")
        dialog = app.window(title_re="Browse")
        dialog.wait("ready", timeout=10)
        root_window: int = dialog.handle
        AddressInput = dialog.child_window(
            class_name="Edit",
            control_id=1152,
        )
        AddressInput.wait("enabled", timeout=10)
        AddressInput.set_edit_text(path)
        time.sleep(0.5)
        OpenButton = dialog.child_window(
            class_name="Button",
            control_id=1,
        )
        OpenButton.wait("enabled", timeout=10)
        OpenButton.click()
        time.sleep(0.5)
        still_exists = any(win.handle == root_window for win in Desktop(backend="win32").windows())
        if still_exists:
            time.sleep(0.5)
            continue
        else:
            break


def Open(path: str):
    while True:
        found = False
        for win in Desktop(backend="win32").windows():
            if win.window_text() == "Open":
                found = True
                break
        if found:
            break
        time.sleep(1)
    while True:
        app = Application(backend="win32").connect(title_re="Open")
        dialog: WindowSpecification = app.window(title_re="Open")
        dialog.wait("ready", timeout=10)
        root_window: int = dialog.handle
        AddressInput = dialog.child_window(class_name="Edit")
        AddressInput.wait("enabled", timeout=10)
        AddressInput.set_edit_text(path)
        time.sleep(1)
        OpenButton = dialog.child_window(title="&Open", class_name="Button")
        OpenButton.wait("enabled", timeout=10)
        OpenButton.click()
        time.sleep(1)
        still_exists = any(win.handle == root_window for win in Desktop(backend="win32").windows())
        if still_exists:
            time.sleep(1)
            continue
        else:
            break


def MicrosoftExcel():
    while True:
        found = False
        for win in Desktop(backend="win32").windows():
            if win.window_text() == "Microsoft Excel":
                found = True
                break
        if found:
            break
        time.sleep(1)
    while True:
        app = Application(backend="win32").connect(title="Microsoft Excel")
        dialog: WindowSpecification = app.window(title="Microsoft Excel")
        dialog.wait("ready", timeout=10)
        dialog.child_window(title="OK", class_name="Button").click()
        time.sleep(2)
        still_exists = False
        for win in Desktop(backend="win32").windows():
            if win.window_text() == "Microsoft Excel":
                still_exists = True
                break
        if still_exists:
            continue
        else:
            break


@shared_task(bind=True, name="Tochigi")
def tochigi(self, process_date: datetime | str):
    if isinstance(process_date, str):
        process_date = datetime.strptime(process_date, "%Y-%m-%d %H:%M:%S.%f").date()
    # ----- #
    TaskID = self.request.id
    logger = Log.get_logger(channel=TaskID, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    logger.info(f"Upload Tochigi: {process_date}")
    # ----- Resource File ----- #
    macro_file = "src/resource/マクロチェック(240819ver).xlsm"
    # ----- Process ----- #
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        with (
            SharePoint(
                domain=settings.SHAREPOINT_DOMAIN,
                username=settings.SHAREPOINT_EMAIL,
                password=settings.SHAREPOINT_PASSWORD,
                playwright=p,
                browser=browser,
                context=context,
            ) as sp,
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            _, month, day = str(process_date).split("-")
            DataTochigi = os.path.join(temp_dir, f"DataTochigi{process_date}.xlsx")
            api = APISharePoint(
                TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
                CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
                CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
            )
            UP = api.get_site("UP")
            Mouka = api.get_site("mouka")
            DataTochigi_ItemID = None
            DataTochigi_DriveID = None
            DataTochigi_SiteID = None
            Uploaded = api.download_item(
                site_id=UP.get("id"),
                breadcrumb=f"データUP一覧/{os.path.basename(DataTochigi)}",
                save_to=os.path.join(temp_dir, f"DataTochigi{process_date}.xlsx"),
            )

            if Uploaded:
                DataTochigi_Upload = api.upload_item(
                    site_id=UP.get("id"),
                    local_path=os.path.join(temp_dir, f"DataTochigi{process_date}.xlsx"),
                    breadcrumb="データUP一覧",
                )
                DataTochigi_ItemID = DataTochigi_Upload.get("id")
                DataTochigi_DriveID = DataTochigi_Upload.get("parentReference").get("driveId")
                DataTochigi_SiteID = DataTochigi_Upload.get("parentReference").get("siteId")
            else:
                logger.info("Download data")
                data = WebAccess(
                    username=settings.WEBACCESS_USERNAME,
                    password=settings.WEBACCESS_PASSWORD,
                    playwright=p,
                    browser=browser,
                    context=context,
                ).download_data(process_date)
                # Lấy dữ liệu mới
                data = data[["案件番号", "得意先名", "物件名", "確定納期", "階", "資料リンク"]]
                data["R_Status"] = pd.NA
                data.to_excel(
                    DataTochigi,
                    index=False,
                )
                # ------ Upload Data File  ------ #
                DataTochigi_Upload = api.upload_item(
                    site_id=UP.get("id"),
                    local_path=os.path.abspath(DataTochigi),
                    breadcrumb="データUP一覧",
                )
                DataTochigi_ItemID = DataTochigi_Upload.get("id")
                DataTochigi_DriveID = DataTochigi_Upload.get("parentReference").get("driveId")
                DataTochigi_SiteID = DataTochigi_Upload.get("parentReference").get("siteId")

            # Xử lí từng dòng
            while True:
                api.download_item(
                    site_id=UP.get("id"),
                    breadcrumb=f"データUP一覧/{os.path.basename(DataTochigi)}",
                    save_to=os.path.abspath(DataTochigi),
                )
                data = pd.read_excel(os.path.abspath(DataTochigi))
                if data["R_Status"].notna().all():
                    break
                for upload_file_index, row in data.iterrows():
                    if pd.notna(row["R_Status"]):
                        continue
                    # ---- Đánh dấu bot đang xử lí dòng/bài này ----
                    while True:
                        if api.write(
                            site_id=DataTochigi_SiteID,
                            drive_id=DataTochigi_DriveID,
                            item_id=DataTochigi_ItemID,
                            range=f"G{upload_file_index+2}",
                            data=[["Đang xử lí"]],
                        ):
                            break
                        time.sleep(0.5)
                    案件番号, _, _, _, 階, 資料リンク, _ = row[:7]
                    logger.info(案件番号)
                    if pd.isna(階):
                        logger.warning("Không xác định số tầng")
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"G{upload_file_index+2}",
                                data=[["Không xác định số tầng"]],
                            ):
                                break
                            time.sleep(0.5)
                        break
                    breadcrumb = sp.get_breadcrumb(資料リンク)
                    if breadcrumb is None:
                        logger.warning("Lỗi link")
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"G{upload_file_index+2}",
                                data=[["Lỗi link"]],
                            ):
                                break
                            time.sleep(0.5)
                        break
                    if breadcrumb[-1].endswith("納材"):
                        logger.warning("Tên folder có ghi ngày")
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"G{upload_file_index+2}",
                                data=[["Tên folder có ghi ngày"]],
                            ):
                                break
                            time.sleep(0.5)
                        break
                    while True:
                        logger.info("download data")
                        if os.path.exists(os.path.abspath(f"downloads/{案件番号}")):
                            shutil.rmtree(os.path.abspath(f"downloads/{案件番号}"))
                        downloads = sp.download(
                            url=資料リンク,
                            file=re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam|pdf)$", re.IGNORECASE),
                            steps=[re.compile("^★データ$")],
                            save_to=temp_dir,
                        )
                        counts: list[str] = [filepath for filepath in downloads]
                        floors: int = 2 if 階 == "-" else len(階.split(","))
                        logger.info("Kiểm tra số lượng")
                        # ---- Đếm số lượng file #
                        has_pdf = any(f.lower().endswith(".pdf") for f in counts)
                        excel_exts = (".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm")
                        excel_count = sum(1 for f in counts if f.lower().endswith(excel_exts))
                        if not has_pdf or excel_count < floors:
                            while True:
                                logger.warning("Không đủ data")
                                if api.write(
                                    site_id=DataTochigi_SiteID,
                                    drive_id=DataTochigi_DriveID,
                                    item_id=DataTochigi_ItemID,
                                    range=f"G{upload_file_index+2}",
                                    data=[["Không đủ data"]],
                                ):
                                    break
                                time.sleep(0.5)
                            break
                        pdf_dir = os.path.abspath(f"downloads/{案件番号}/pdf")
                        excel_dir = os.path.abspath(f"downloads/{案件番号}/excel")
                        os.makedirs(name=pdf_dir, exist_ok=True)
                        os.makedirs(name=excel_dir, exist_ok=True)

                        temp: list[str] = []
                        for filepath in downloads:
                            filename = os.path.basename(filepath)
                            ext = os.path.splitext(filename)[1].lower()
                            if ext == ".pdf":
                                new_path = os.path.join(pdf_dir, filename)
                                shutil.move(filepath, new_path)
                                temp.append(new_path)
                            elif ext in excel_exts:
                                new_path = os.path.join(excel_dir, filename)
                                shutil.move(filepath, new_path)
                                temp.append(new_path)
                        logger.info("Chạy macro")
                        with FileLock(os.path.join("src/resource","macro.lock"), timeout=300):
                            try:
                                app = xw.App(visible=False)
                                wb_macro = app.books.open(macro_file)
                                # Fname
                                for win in Desktop(backend="win32").windows():
                                    if win.window_text() == "Browse":
                                        with suppress(Exception):
                                            app = Application(backend="win32").connect(handle=win.handle)
                                            dialog = app.window(handle=win.handle)
                                            dialog.close()
                                threading.Thread(target=Fname, args=(excel_dir,)).start()
                                wb_macro.macro("Fname")()
                                # Fopen
                                wb_macro.macro("Fopen")()
                                wb_macro.save()
                                wb_macro.close()
                            finally:
                                app.quit()
                            macro_data = pd.read_excel(
                                io=macro_file,
                                sheet_name="メインメニュー",
                                header=None,
                            )
                        macro_data.index = macro_data.index + 1
                        macro_data.columns = [get_column_letter(i + 1) for i in range(macro_data.shape[1])]
                        result = set(macro_data["G"][2:])
                        result = {x for x in result if pd.notna(x)}
                        if result != {"OK"}:
                            logger.warning("Lỗi macro")
                            while True:
                                if api.write(
                                    site_id=DataTochigi_SiteID,
                                    drive_id=DataTochigi_DriveID,
                                    item_id=DataTochigi_ItemID,
                                    range=f"G{upload_file_index+2}",
                                    data=[["Lỗi macro"]],
                                ):
                                    break
                                time.sleep(0.5)
                            break
                        # Upload
                        logger.info("Up data")
                        downloads: list[str] = temp
                        納品日 = f"{int(month)}月{int(day)}日"
                        while True:
                            up: list[dict] = []
                            for f in os.listdir(pdf_dir):
                                up.append(
                                    api.upload_item(
                                        site_id=Mouka.get("id"),
                                        local_path=os.path.join(pdf_dir, f),
                                        breadcrumb=f"真岡工場　製造データ/{納品日}/栃木工場確定データ",
                                    )
                                )
                            for f in os.listdir(excel_dir):
                                up.append(
                                    api.upload_item(
                                        site_id=Mouka.get("id"),
                                        local_path=os.path.join(excel_dir, f),
                                        breadcrumb=f"真岡工場　製造データ/{納品日}/栃木工場確定データ",
                                    )
                                )
                            if all("error" not in item for item in up):
                                while True:
                                    if api.write(
                                        site_id=DataTochigi_SiteID,
                                        drive_id=DataTochigi_DriveID,
                                        item_id=DataTochigi_ItemID,
                                        range=f"G{upload_file_index+2}",
                                        data=[["Chưa có trên Power App"]],
                                    ):
                                        break
                                    time.sleep(0.5)
                                break
                        logger.info("Đổi tên")
                        suffix = f"{month}-{day}納材"
                        sp.rename_breadcrumb(
                            資料リンク,
                            f"{breadcrumb[-1]} {suffix}",
                        )
                        break
                    break

            time.sleep(2.5)
