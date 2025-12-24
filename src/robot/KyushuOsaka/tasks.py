import os
import re
import shutil
import tempfile
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import redis
import xlwings as xw
from celery import shared_task
from filelock import FileLock
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.KyushuOsaka.api import APISharePoint
from src.robot.KyushuOsaka.automation import PowerApp, SharePoint


def Fname(path: str):
    import time

    from pywinauto import Desktop
    from pywinauto.application import Application

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


@shared_task(bind=True, name="Kyushu Osaka")
def kyushu_osaka(
    self,
    process_date: datetime,
    kyushu: bool | str = True,
    osaka: bool | str = True,
    up_trong: bool | str = False,
):
    TaskID = self.request.id
    logger = Log.get_logger(channel=TaskID, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    logger.info(f"Upload Kyushu-Osaka: {process_date}")
    # Xử lí đầu vào
    if isinstance(process_date, str):
        process_date = datetime.strptime(process_date, "%Y-%m-%d %H:%M:%S.%f").date()
    if isinstance(kyushu, str):
        if kyushu.lower() == "false":
            kyushu = False
        elif kyushu.lower() == "true":
            kyushu = True
        else:
            kyushu = False
    if isinstance(osaka, str):
        if osaka.lower() == "false":
            osaka = False
        elif osaka.lower() == "true":
            osaka = True
        else:
            osaka = False
    if isinstance(up_trong, str):
        if up_trong.lower() == "false":
            up_trong = False
        elif up_trong.lower() == "true":
            up_trong = True
        else:
            up_trong = False
    # -------------
    factory = []
    if kyushu:
        factory.append("九州")
    if osaka:
        factory.append("大阪")
    # -------------
    api = APISharePoint(
        TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
        CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
        CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
    )
    # --- #
    folder_id = None
    items = api.get_item_from_another_item(
        "nskkogyo.sharepoint.com,f8711c8d-9046-4e1c-9de9-e720d1c0c797,90e7b19b-ba14-4986-9e05-cbc7e7358c90",  # UP
        "b!jRxx-EaQHE6d6ecg0cDHl5ux55AUuoZJngXLx-c1jJCx-m83m_1wTqubHf8e5WFu",  # ....
        "01NRWYYNB7F5WKOEZTLRCISBYBBWMFETFG",  # データUP一覧
    ).get("value")
    for item in items:
        if item.get("name") == f"{int(process_date.month)}月{int(process_date.day)}日":
            folder_id = item.get("id")
            break
    if folder_id is None:
        logger.info("Không tìm thấy folder")
        raise FileNotFoundError("Không tìm thấy folder")
    # --- #
    files = api.get_item_from_another_item(
        "nskkogyo.sharepoint.com,f8711c8d-9046-4e1c-9de9-e720d1c0c797,90e7b19b-ba14-4986-9e05-cbc7e7358c90",
        "b!jRxx-EaQHE6d6ecg0cDHl5ux55AUuoZJngXLx-c1jJCx-m83m_1wTqubHf8e5WFu",
        folder_id,
    ).get("value")
    if not files:
        logger.info("Không tìm thấy file data")
        raise FileNotFoundError("Không tìm thấy file data")
    files = [(file.get("id"), file.get("name")) for file in files]
    # --- #
    if (
        len(
            [
                (id, name)
                for id, name in files
                if isinstance(name, str) and name.lower().endswith((".xls", ".xlsx", ".xlsm"))
            ]
        )
        != 1
    ):
        logger.info("Không xác định được file data")
        raise FileNotFoundError("Không xác định được file data")
    # --- #
    temp_file = [
        (id, name) for id, name in files if isinstance(name, str) and name.lower().endswith((".xls", ".xlsx", ".xlsm"))
    ]
    item_id = temp_file[0][0]
    item_name = temp_file[0][1]
    # --- #
    macro_file = "src/robot/KyushuOsaka/resource/マクロチェック(240819ver).xlsm"

    item_id = item_id
    driver_id = folder_id
    site_id = "nskkogyo.sharepoint.com,f8711c8d-9046-4e1c-9de9-e720d1c0c797,90e7b19b-ba14-4986-9e05-cbc7e7358c90"
    # --- item --- #
    file: dict = {
        "site_id": site_id,
        "drive_id": driver_id,
        "item_id": item_id,
        "item_name": item_name,
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
            ],
        )
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
            PowerApp(
                username=settings.POWER_APP_USERNAME,
                password=settings.POWER_APP_PASSWORD,
                playwright=p,
                browser=browser,
                context=context,
            ) as pa,
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            while True:
                drive_id, _ = api.download_item(
                    site_id=file.get("site_id"),
                    breadcrumb=f"データUP一覧/{int(process_date.month)}月{int(process_date.day)}日/{file.get("item_name")}",
                    save_to=temp_dir,
                )
                data = pd.read_excel(io=os.path.join(temp_dir, file.get("item_name")), sheet_name="データUP状況")
                data.index = data.index + 2
                mask_factory = data["出荷工場"].isin(factory)
                mask_r_empty = data["R_Status"].isna() | data["R_Status"].astype(str).str.strip().eq("")
                mask_d_empty = data["DATAUP状況"].isna() | data["DATAUP状況"].astype(str).str.strip().eq("")
                data = data[mask_factory & mask_r_empty & mask_d_empty]
                if data.shape[0] == 0:
                    return
                suffix_name = f"{process_date.strftime("%m-%d")}納材"
                for index, row in data.iterrows():
                    logger.info(f"Index: {index}")
                    api.write(
                        site_id=file.get("site_id"),
                        drive_id=drive_id,
                        item_id=file.get("item_id"),
                        range=f"E{index}",
                        data=[["Đang xử lí"]],
                        sheet="データUP状況",
                    )
                    if pd.isna(row["資料リンク"]):
                        logger.warning("Không có link data")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Không có link data"]],
                            sheet="データUP状況",
                        )
                        break
                    if pd.isna(row["階"]):
                        logger.warning("Không có số tầng")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Không có số tầng"]],
                            sheet="データUP状況",
                        )
                        break
                    breadcrumb = sp.get_breadcrumb(row["資料リンク"])
                    if breadcrumb[-1].endswith("納材"):
                        logger.warning("Tên folder có ghi ngày")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Tên folder có ghi ngày"]],
                            sheet="データUP状況",
                        )
                        break
                    download_path = os.path.join(temp_dir, str(int(row["案件番号"])))
                    shutil.rmtree(download_path, ignore_errors=True)
                    downloads = sp.download(
                        url=row["資料リンク"],
                        file=re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam|pdf)$", re.IGNORECASE),
                        steps=[re.compile("^★データ$")],
                        save_to=download_path,
                    )
                    if not downloads:
                        logger.warning("Không đủ data")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Không đủ data"]],
                            sheet="データUP状況",
                        )
                        break
                    count_floor = len(row["階"].split(",")) if hasattr(row["階"], "split") else None
                    if count_floor is None:
                        logger.warning("Lỗi: kiểm tra cột 階")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Lỗi: kiểm tra cột 階"]],
                            sheet="データUP状況",
                        )
                        break
                    excel_files = len(
                        [
                            f
                            for f in downloads
                            if re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam)$", re.IGNORECASE).match(f)
                        ]
                    )
                    pdf_files = len([f for f in downloads if re.compile(r".*\.pdf$", re.IGNORECASE).match(f)])
                    if pdf_files != 1:
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[[f"{pdf_files} file PDF"]],
                            sheet="データUP状況",
                        )
                        break
                    if excel_files < count_floor:
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[[f"{excel_files} file / {count_floor} floors"]],
                            sheet="データUP状況",
                        )
                        break
                    # --- Kiểm tra tên file --- #
                    isError: bool = False
                    for downloaded in downloads:
                        downloaded_file = unicodedata.normalize("NFKC", downloaded)
                        if not any(
                            part in downloaded_file
                            for part in re.split(r"[ \u3000・\u2018]+", unicodedata.normalize("NFKC", breadcrumb[-1]))
                        ):
                            isError = True
                            break
                    if isError:
                        logger.warning("Lỗi filename")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Lỗi filename"]],
                            sheet="データUP状況",
                        )
                        break
                    # --- Kiểm tra macro
                    os.makedirs(os.path.join(download_path, "excel"), exist_ok=True)
                    os.makedirs(os.path.join(download_path, "pdf"), exist_ok=True)
                    while True:
                        for download in downloads:
                            f = os.path.basename(download)
                            if re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam)$", re.IGNORECASE).match(f):
                                shutil.move(
                                    src=download,
                                    dst=os.path.join(os.path.dirname(downloads[0]), "excel"),
                                )
                            else:
                                shutil.move(
                                    src=download,
                                    dst=os.path.join(os.path.dirname(downloads[0]), "pdf"),
                                )
                        if os.listdir(download_path) == ["excel", "pdf"]:
                            break
                    logger.info("Chạy macro")
                    try:
                        with FileLock(os.path.join("src/resource", "macro.lock"), timeout=300):
                            app = xw.App(visible=False)
                            wb_macro = app.books.open(macro_file)
                            threading.Thread(
                                target=Fname, args=(os.path.abspath(os.path.join(download_path, "excel")),)
                            ).start()
                            wb_macro.macro("Fname")()
                            # Fopen
                            wb_macro.macro("Fopen")()
                            wb_macro.save()
                            wb_macro.close()
                            app.quit()
                    except Exception:
                        logger.warning("Lỗi macro")
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Lỗi: Chạy macro lỗi"]],
                            sheet="データUP状況",
                        )
                        break
                    logger.info("Up data")
                    if row["出荷工場"] == "九州":
                        path = [
                            re.compile("^九州工場 製造データー$"),
                            re.compile(f"{int(process_date.month)}月{int(process_date.day)}日配送分"),
                            re.compile(r"^確定データ\(.+\)$"),
                        ]
                        if not up_trong:
                            path = [
                                re.compile("^九州工場 製造データー$"),
                                re.compile(f"{int(process_date.month)}月{int(process_date.day)}日配送分"),
                            ]
                        if not sp.upload(
                            url="https://nskkogyo.sharepoint.com/sites/kyuusyuukouzyou",
                            files=[f for f in Path(download_path).rglob("*") if f.is_file()],
                            steps=path,
                        ):
                            api.write(
                                site_id=file.get("site_id"),
                                drive_id=drive_id,
                                item_id=file.get("item_id"),
                                range=f"E{index}",
                                data=[["Lỗi: Up Data"]],
                                sheet="データUP状況",
                            )
                            break
                    elif row["出荷工場"] == "大阪":
                        if not sp.upload(
                            url="https://nskkogyo.sharepoint.com/sites/yanase/Shared Documents/Forms/AllItems.aspx?id=/sites/yanase/Shared Documents/大阪工場　製造データ",  # noqa: E501
                            files=[f for f in Path(download_path).rglob("*") if f.is_file()],
                            steps=[
                                re.compile(rf"^{process_date.month:02d}(月|日){process_date.day:02d}日$"),
                                re.compile(r"^🔹関西工場確定データ🔹"),
                            ],
                        ):
                            api.write(
                                site_id=file.get("site_id"),
                                drive_id=drive_id,
                                item_id=file.get("item_id"),
                                range=f"E{index}",
                                data=[["Lỗi: Up Data"]],
                                sheet="データUP状況",
                            )
                            break
                    else:
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Lỗi: kiểm tra xưởng"]],
                            sheet="データUP状況",
                        )
                        break
                    logger.info("Đổi tên")
                    if not sp.rename_breadcrumb(
                        url=row["資料リンク"],
                        new_name=f"{breadcrumb[-1]} {suffix_name}",
                    ):
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Chưa có trên Power App | Lỗi: đổi tên folder"]],
                            sheet="データUP状況",
                        )
                        break
                    else:
                        api.write(
                            site_id=file.get("site_id"),
                            drive_id=drive_id,
                            item_id=file.get("item_id"),
                            range=f"E{index}",
                            data=[["Chưa có trên Power App"]],
                            sheet="データUP状況",
                        )
                    if row["出荷工場"] == "大阪":
                        break  # Osaka không nhấn app
                    logger.info("Nhấn app")
                    for building in list(
                        set(
                            [
                                row["物件名"],
                                row["物件名"].replace("\u3000", "").replace(" ", ""),
                            ]
                        )
                    ):
                        if pa.up(
                            process_date=f"{process_date.month}月{process_date.day}日",
                            factory="九州工場",
                            build=building,
                        ):
                            api.write(
                                site_id=file.get("site_id"),
                                drive_id=drive_id,
                                item_id=file.get("item_id"),
                                range=f"E{index}",
                                data=[["OK"]],
                                sheet="データUP状況",
                            )
                            api.write(
                                site_id=file.get("site_id"),
                                drive_id=drive_id,
                                item_id=file.get("item_id"),
                                range=f"Q{index}",
                                data=[["UP"]],
                                sheet="データUP状況",
                            )
                            break
                    break
