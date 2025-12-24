import os
import re
import shutil
import tempfile
import threading
import unicodedata
from datetime import datetime

import pandas as pd
import redis
import xlwings as xw
from celery import shared_task
from filelock import FileLock
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.ShigaToyoChiba.api import APISharePoint
from src.robot.ShigaToyoChiba.automation import PowerApp, SharePoint, WebAccess


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


@shared_task(bind=True, name="Shiga Toyo Chiba")
def shiga_toyo_chiba(
    self,
    process_date: datetime | str,
    up_trong: bool | str = False,
):
    if isinstance(up_trong, str):
        if up_trong.lower() == "false":
            up_trong = False
        elif up_trong.lower() == "true":
            up_trong = True
        else:
            up_trong = False
    # --- #
    TaskID = self.request.id
    logger = Log.get_logger(channel=TaskID, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    with tempfile.TemporaryDirectory() as temp_dir:
        DataShigaUp_ItemID = None
        DataShigaUp_DriveID = None
        DataShigaUp_SiteID = None
        # ---- #
        APIClient = APISharePoint(
            TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
            CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
            CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
        )
        if isinstance(process_date, str):
            process_date = datetime.strptime(process_date, "%Y-%m-%d %H:%M:%S.%f").date()
        logger.info(f"Upload 3 xưởng: {process_date}")
        # ---- File Data
        FileData = f"DataShigaToyoChiba{process_date.strftime("%m-%d")}.xlsx"
        # ---- UP site
        UPSite = APIClient.get_site("UP")
        # ---- Upload File Data
        if not APIClient.download_item(
            site_id=UPSite.get("id"),
            breadcrumb=f"データUP一覧/{FileData}",
            save_to=os.path.join(temp_dir, FileData),
        ):
            logger.info("Download data from Access")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, args=["--start-maximized"])
                context = browser.new_context(no_viewport=True)
                with WebAccess(
                    username=settings.WEBACCESS_USERNAME,
                    password=settings.WEBACCESS_PASSWORD,
                    playwright=p,
                    browser=browser,
                    context=context,
                ) as wa:
                    orders = wa.download_data(process_date)
                    UploadStatus_Columns = [
                        "出荷工場",
                        "案件番号",
                        "得意先名",
                        "物件名",
                        "R_Status",
                        "確定納期",
                        "追加不足",
                        "目地数量",
                        "入隅数量",
                        "階",
                        "配送先住所",
                        "受注NO",
                        "資料リンク",
                        "事業所",
                        "軽天有無",
                        "出荷手段",
                        "DATAUP状況",
                    ]
                    columns = []
                    for column in UploadStatus_Columns:
                        if column in orders.columns:
                            columns.append(column)
                    orders = orders[columns]
                    # Insert new Column
                    orders.insert(loc=orders.columns.get_loc("物件名") + 1, column="R_Status", value="")
                    # Save File
                    orders = orders.sort_values(by="出荷工場").reset_index(drop=True)
                    orders.to_excel(os.path.join(temp_dir, FileData), index=False)
                    # Upload to SharePoint
                    item = APIClient.upload_item(
                        site_id=UPSite.get("id"),
                        breadcrumb="データUP一覧",
                        local_path=os.path.join(temp_dir, FileData),
                        replace=False,
                    )
                    DataShigaUp_ItemID = item.get("id")
                    DataShigaUp_DriveID = item.get("parentReference").get("driveId")
                    DataShigaUp_SiteID = item.get("parentReference").get("siteId")
        else:
            item = APIClient.upload_item(
                site_id=UPSite.get("id"),
                breadcrumb="データUP一覧",
                local_path=os.path.join(temp_dir, FileData),
                replace=False,
            )
            DataShigaUp_ItemID = item.get("id")
            DataShigaUp_DriveID = item.get("parentReference").get("driveId")
            DataShigaUp_SiteID = item.get("parentReference").get("siteId")
        # ---- Upload Data
        suffix_name = f"{process_date.strftime("%m-%d")}納材"
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
                PowerApp(
                    username=settings.POWER_APP_USERNAME,
                    password=settings.POWER_APP_PASSWORD,
                    playwright=p,
                    browser=browser,
                    context=context,
                ) as pa,
            ):
                while True:
                    APIClient.download_item(
                        site_id=UPSite.get("id"),
                        breadcrumb=f"データUP一覧/{FileData}",
                        save_to=temp_dir,
                    )
                    data = pd.read_excel(os.path.join(temp_dir, FileData))
                    #
                    cleaned_data = data[
                        ~data["得意先名"].isin(
                            [
                                "㈱吉村一建設(ナカザワ美原)",
                                "紀の国住宅㈱",
                                "㈱ヤマカ木材(大日本木材防腐)",
                                "㈱ホーク・ワン",
                                "三光ソフラン株式会社",
                                "ゼロ・コーポレーション",
                                "㈱創建(ナカザワ美原)",
                                "ｼﾉｹﾝﾌﾟﾛﾃﾞｭｰｽ",
                                "ﾗｲｱｰﾄ㈱",
                                "雅美建設㈱",
                                "㈱アイケンジャパン",
                                "株式会社 和協",
                                "住友不動産株式会社 リフォーム",
                                "㈱トータテハウジング",
                                "㈱デザオ建設",
                            ]
                        )
                    ]
                    if cleaned_data["R_Status"].notna().all():
                        break
                    # Tiếp tục xử lí
                    for index, row in data.iterrows():
                        if row["得意先名"] in [
                            "㈱吉村一建設(ナカザワ美原)",
                            "紀の国住宅㈱",
                            "㈱ヤマカ木材(大日本木材防腐)",
                            "㈱ホーク・ワン",
                            "三光ソフラン株式会社",
                            "ゼロ・コーポレーション",
                            "㈱創建(ナカザワ美原)",
                            "ｼﾉｹﾝﾌﾟﾛﾃﾞｭｰｽ",
                            "ﾗｲｱｰﾄ㈱",
                            "雅美建設㈱",
                            "㈱アイケンジャパン",
                            "株式会社 和協",
                            "住友不動産株式会社 リフォーム",
                            "㈱トータテハウジング",
                            "㈱デザオ建設",
                        ]:
                            # Bỏ qua bài ở dòng này
                            continue
                        if pd.notna(row["R_Status"]):
                            # Bài ở dòng này đã xử lí rồi
                            continue
                        if pd.isna(row["階"]):
                            # Bài ở dòng này không có số tầng
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi: kiểm tra cột 階"]],
                            )
                            break
                        logger.info(row)
                        APIClient.write(
                            siteId=DataShigaUp_SiteID,
                            driveId=DataShigaUp_DriveID,
                            itemId=DataShigaUp_ItemID,
                            range=f"E{index+2}",
                            data=[["Đang xử lí"]],
                        )
                        # Get breadcrumb
                        logger.info("Get breadcrumb")
                        url = row["資料リンク"]
                        breadcrumb = sp.get_breadcrumb(url)
                        if breadcrumb[-1].endswith("納材"):
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Tên folder có ghi ngày"]],
                            )
                            break
                        download_path = os.path.join(temp_dir, str(int(row["案件番号"])))
                        shutil.rmtree(download_path, ignore_errors=True)
                        logger.info("Download data")
                        downloads = sp.download(
                            url=url,
                            file=re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam|pdf)$", re.IGNORECASE),
                            steps=[re.compile("^★データ$")],
                            save_to=download_path,
                        )
                        if not downloads:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["không đủ data"]],
                            )
                            break
                        if row["出荷工場"] not in ["滋賀", "豊橋", "千葉"]:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi: kiểm tra cột 出荷工場"]],
                            )
                            break
                        logger.info("Count data")
                        # --- Kiểm tra số lượng file --- #
                        count_floor = len(row["階"].split(",")) if hasattr(row["階"], "split") else None
                        if count_floor is None:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi: kiểm tra cột 階"]],
                            )
                            break
                        excel_files = len(
                            [
                                f
                                for f in downloads
                                if re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam)$", re.IGNORECASE).match(
                                    f
                                )
                            ]
                        )
                        pdf_files = len([f for f in downloads if re.compile(r".*\.pdf$", re.IGNORECASE).match(f)])
                        if pdf_files != 1:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[[f"{pdf_files} file PDF"]],
                            )
                            break
                        if excel_files < count_floor:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[[f"{len(excel_files)} file / {count_floor} floors"]],
                            )
                            break
                        logger.info("Check filename")
                        isError: bool = False
                        # --- Kiểm tra tên file --- #
                        for downloaded in downloads:
                            downloaded_file = unicodedata.normalize("NFKC", downloaded)
                            if not any(
                                part in downloaded_file
                                for part in re.split(
                                    r"[ \u3000・\u2018]+", unicodedata.normalize("NFKC", breadcrumb[-1])
                                )
                            ):
                                isError = True
                                break
                        if isError:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi filename"]],
                            )
                            break
                        # --- Kiểm tra macro
                        # ---- Chia dữ liệu thành 2 folder Excel / PDF
                        os.makedirs(os.path.join(download_path, "excel"), exist_ok=True)
                        os.makedirs(os.path.join(download_path, "pdf"), exist_ok=True)
                        while True:
                            for download in downloads:
                                f = os.path.basename(download)
                                if re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam)$", re.IGNORECASE).match(
                                    f
                                ):
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
                        logger.info("Run macro")
                        try:
                            with FileLock(os.path.join("src/resource","macro.lock"), timeout=300):
                                app = xw.App(visible=False)
                                macro_file = "src/resource/マクロチェック(240819ver).xlsm"
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
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi: Chạy macro lỗi"]],
                            )
                            break
                        # --- Upload Data
                        logger.info("Upload data")
                        upload_data = []
                        for dirpath, _, filenames in os.walk(download_path):
                            for filename in filenames:
                                upload_data.append(os.path.join(dirpath, filename))
                        if row["出荷工場"] == "滋賀":  # Shiga
                            path = [
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                ),
                            ]
                            if up_trong:
                                path = [
                                    re.compile(
                                        rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                    ),
                                    re.compile(r"^確定データ\(.+\)$"),
                                ]
                            if not sp.upload(
                                url="https://nskkogyo.sharepoint.com/sites/shiga/Shared Documents/Forms/AllItems.aspx?id=/sites/shiga/Shared Documents/滋賀工場 製造データ",  # noqa
                                files=upload_data,
                                steps=path,
                            ):
                                APIClient.write(
                                    siteId=DataShigaUp_SiteID,
                                    driveId=DataShigaUp_DriveID,
                                    itemId=DataShigaUp_ItemID,
                                    range=f"E{index+2}",
                                    data=[["Lỗi: up data"]],
                                )
                                break
                        elif row["出荷工場"] == "豊橋":  # Toyo
                            path = [
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                ),
                            ]
                            if up_trong:
                                path = [
                                    re.compile(
                                        rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                    ),
                                    re.compile(r"^確定データ\(.+\)$"),
                                ]
                            if not sp.upload(
                                url="https://nskkogyo.sharepoint.com/sites/toyohashi/Shared Documents/Forms/AllItems.aspx?id=/sites/toyohashi/Shared Documents/豊橋工場 製造データ",  # noqa
                                files=upload_data,
                                steps=path,
                            ):
                                APIClient.write(
                                    siteId=DataShigaUp_SiteID,
                                    driveId=DataShigaUp_DriveID,
                                    itemId=DataShigaUp_ItemID,
                                    range=f"E{index+2}",
                                    data=[["Lỗi: up data"]],
                                )
                                break
                        elif row["出荷工場"] == "千葉":  # Chiba
                            path = [
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                ),
                            ]
                            if up_trong:
                                path = [
                                    re.compile(
                                        rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                    ),
                                    re.compile(r"^確定データ\(.+\)$"),
                                ]
                            if not sp.upload(
                                url="https://nskkogyo.sharepoint.com/sites/nskhome/Shared Documents/Forms/AllItems.aspx?id=/sites/nskhome/Shared Documents/千葉工場 製造データ",  # noqa
                                files=upload_data,
                                steps=path,
                            ):
                                APIClient.write(
                                    siteId=DataShigaUp_SiteID,
                                    driveId=DataShigaUp_DriveID,
                                    itemId=DataShigaUp_ItemID,
                                    range=f"E{index+2}",
                                    data=[["Lỗi: up data"]],
                                )
                                break
                        else:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["Lỗi: kiểm tra cột 出荷工場"]],
                            )
                            break
                        sp.rename_breadcrumb(url=url, new_name=f"{breadcrumb[-1]} {suffix_name}")
                        APIClient.write(
                            siteId=DataShigaUp_SiteID,
                            driveId=DataShigaUp_DriveID,
                            itemId=DataShigaUp_ItemID,
                            range=f"E{index+2}",
                            data=[["Chưa có trên Power App"]],
                        )
                        # --- #
                        up: bool = False
                        if row["出荷工場"] == "滋賀":  # Shiga
                            for p in list(
                                set(
                                    [
                                        row["物件名"],
                                        row["物件名"].replace("　", "").replace(" ", ""),
                                    ]
                                )
                            ):
                                up = pa.up(
                                    process_date=f"{process_date.month}月{process_date.day}日",
                                    factory="滋賀工場",
                                    build=p,
                                )
                                if up:
                                    break
                        elif row["出荷工場"] == "豊橋":  # Toyo
                            for p in list(
                                set(
                                    [
                                        row["物件名"],
                                        row["物件名"].replace("　", "").replace(" ", ""),
                                    ]
                                )
                            ):
                                up = pa.up(
                                    process_date=f"{process_date.month}月{process_date.day}日",
                                    factory="豊橋工場",
                                    build=p,
                                )
                                if up:
                                    break
                        elif row["出荷工場"] == "千葉":  # Chiba
                            for p in list(
                                set(
                                    [
                                        row["物件名"],
                                        row["物件名"].replace("　", "").replace(" ", ""),
                                    ]
                                )
                            ):
                                up = pa.up(
                                    process_date=f"{process_date.month}月{process_date.day}日",
                                    factory="千葉工場",
                                    build=p,
                                )
                                if up:
                                    break
                        if up:
                            APIClient.write(
                                siteId=DataShigaUp_SiteID,
                                driveId=DataShigaUp_DriveID,
                                itemId=DataShigaUp_ItemID,
                                range=f"E{index+2}",
                                data=[["OK"]],
                            )
                        break
