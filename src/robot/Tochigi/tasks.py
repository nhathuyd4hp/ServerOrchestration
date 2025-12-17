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
from pywinauto.keyboard import send_keys

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.Tochigi.api import APISharePoint
from src.robot.Tochigi.automation import PowerApp, SharePoint


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


@shared_task(bind=True)
def old_tochigi(self, process_date: datetime | str):
    if isinstance(process_date, str):
        process_date = datetime.strptime(process_date, "%Y-%m-%d %H:%M:%S.%f").date()
    # ----- #
    TaskID = self.request.id
    logger = Log.get_logger(channel=TaskID, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    logger.info(f"Upload Tochigi: {process_date}")
    # ----- Resource File ----- #
    database = "src/robot/Tochigi/resource/(真岡工場)改訂0607 Complex Additions.xlsm"
    macro_file = "src/robot/Tochigi/resource/マクロチェック(240819ver).xlsm"
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
            PowerApp(
                username=settings.POWER_APP_USERNAME,
                password=settings.POWER_APP_PASSWORD,
                playwright=p,
                browser=browser,
                context=context,
            ) as pa,
            tempfile.TemporaryDirectory() as temp_dir,
        ):
            year, month, day = str(process_date).split("-")  # '2026/01/01'
            DataTochigi = os.path.join(temp_dir, f"DataTochigi{process_date}.xlsx")
            api = APISharePoint(
                TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
                CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
                CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
            )
            Site_DQ = api.get_site("DQ")
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
                site = api.get_site("mouka")
                metadata = api.get_metadata(
                    site_id=site.get("id"),
                    breadcrumb=f"Documents/真岡工場　製造データ/{int(month)}月{int(day)}日",
                )
                if "error" in metadata:
                    logger.error(metadata.get("error"))
                    raise FileNotFoundError(
                        f"Không tồn tại: 'Documents/真岡工場　製造データ/{int(month)}月{int(day)}日'"
                    )

                items = api.get_item_from_another_item(
                    site_id=site.get("id"),
                    drive_id=metadata.get("parentReference").get("driveId"),
                    item_id=metadata.get("id"),
                )
                item: list = []
                items = items.get("value")
                for i in items:
                    name: str = i.get("name")
                    if name.endswith(".xls"):
                        if api.download_item(
                            site_id=site.get("id"),
                            breadcrumb=f"真岡工場　製造データ/{int(month)}月{int(day)}日/{i.get("name")}",
                            save_to=os.path.join(temp_dir, i.get("name")),
                        ):
                            item.append(os.path.join(temp_dir, i.get("name")))
                for i in item[:]:
                    file: str = os.path.basename(i)
                    pattern = rf"^配車{year}年{int(month)}月{int(day)}日【小山】.*\.xls$"
                    if not re.match(pattern, file):
                        item.remove(i)
                        os.remove(i)
                if len(item) == 0:
                    logger.error("Không tìm thấy file phân xe")
                    return True
                if len(item) > 1:
                    logger.error(f"Tìm thấy {len(item)} file phân xe")
                    return True
                item: str = item[0]
                # Chạy macro file Database
                app = xw.App(visible=False)
                try:
                    db = app.books.open(database)
                    # ---- #
                    db.macro("erasedata")()
                    # ---- #
                    threading.Thread(target=確認).start()
                    threading.Thread(target=Open, args=(item,)).start()
                    threading.Thread(target=MicrosoftExcel).start()
                    db.macro("マスターデータ取込02")()
                    db.save()
                    db.close()
                except Exception as e:
                    raise e
                finally:
                    app.quit()
                    os.remove(item)
                    # ---- #
                while True:
                    app = None
                    try:
                        excel_path = r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"  # đường dẫn Excel
                        app = Application(
                            backend="uia",
                            allow_magic_lookup=True,
                        ).start(f'"{excel_path}" "{database}"')
                        file_name = os.path.basename(database)
                        pattern = re.escape(file_name) + ".*- Excel"
                        dlg: WindowSpecification = app.window(title_re=pattern)
                        dlg.wait("visible", timeout=30)
                        while True:
                            dlg.set_focus()
                            EnableContent = dlg.child_window(title="Enable Content", control_type="Button")
                            if EnableContent and EnableContent.exists(timeout=5):
                                EnableContent.click_input()
                            else:
                                break
                        while True:
                            dlg.set_focus()
                            Worksheet = dlg.child_window(title="振り分け用", control_type="TabItem").click_input()
                            if Worksheet and Worksheet.exists(timeout=5):
                                Worksheet.select()
                                break
                            else:
                                break
                        dlg.set_focus()
                        send_keys("%{F8}")
                        while True:
                            dlg.set_focus()
                            macro_dlg = app.window(title="Macro")
                            macro_dlg.wait("visible", timeout=10)
                            Coloring = macro_dlg.child_window(title="Coloring", control_type="ListItem")
                            if Coloring and Coloring.exists(timeout=5):
                                Coloring.select()
                                break
                        while True:
                            dlg.set_focus()
                            Run = macro_dlg.child_window(title="Run", control_type="Button")
                            if Run and Run.exists(timeout=5):
                                Run.click_input()
                                break
                        dlg.set_focus()
                        send_keys("%{F8}")
                        while True:
                            dlg.set_focus()
                            macro_dlg = app.window(title="Macro")
                            macro_dlg.wait("visible", timeout=10)
                            Coloring = macro_dlg.child_window(title="listcreation", control_type="ListItem")
                            if Coloring and Coloring.exists(timeout=5):
                                Coloring.select()
                                break
                        while True:
                            Run = macro_dlg.child_window(title="Run", control_type="Button")
                            if Run and Run.exists(timeout=5):
                                Run.click_input()
                                break
                        time.sleep(2)
                        MicrosoftExcel()
                        dlg.set_focus()
                        send_keys("^s")
                        time.sleep(1)
                        dlg.set_focus()
                        send_keys("%{F4}")
                        time.sleep(1)
                        break
                    except Exception:
                        if app:
                            app.kill()
                data = pd.read_excel(
                    database,
                    sheet_name="振り分け用",
                    usecols="I:Q",
                )
                # Xóa các dòng có chứa note '製造済' ở cột 特記事項 (M)
                data = data[~data["特記事項"].astype(str).str.contains("製造済", na=False)]
                data = data.dropna(subset=[data.columns[0]])
                data["納期"] = data["納期"].dt.strftime("%m月%d日")
                data["納期"] = data["納期"].str.replace(r"0(\d)月", r"\1月", regex=True)
                data["納期"] = data["納期"].str.replace(r"0(\d)日", r"\1日", regex=True)
                data["Note"] = pd.NA
                data["Insert"] = pd.NA
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

            # Dán 1 lần
            while True:
                api.download_item(
                    site_id=UP.get("id"),
                    breadcrumb=f"データUP一覧/{os.path.basename(DataTochigi)}",
                    save_to=os.path.abspath(DataTochigi),
                )
                data = pd.read_excel(os.path.abspath(DataTochigi))
                if data["Insert"].notna().all():
                    break
                for upload_file_index, row in data.iterrows():
                    Title, ビルダー, 案件名, 区分, 特記事項, 納品日, 工場, URL, Floors, _, _ = row
                    if row["案件名　（未アップデータ）"] in [
                        "㈱吉村一建設(ナカザワ美原)",
                        "紀の国住宅㈱",
                        "㈱ヤマカ木材(大日本木材防腐)",
                        "㈱ホーク・ワン",
                        "三光ソフラン株式会社",
                        "ゼロ・コーポレーション",
                        "㈱創建(ナカザワ美原)",
                        "ｼﾉｹﾝﾌﾟﾛﾃﾞｭｰｽ",
                    ]:
                        continue
                    if pd.notna(row["Insert"]) and pd.notna(row["Note"]):
                        continue
                    while True:
                        if api.add_to_list(
                            site_id=Site_DQ.get("id"),
                            list_id="8d1b2a59-ea2b-4ffa-83b3-39f3248ee023",
                            fields={
                                "Title": clean_value(Title),
                                "_x30d3__x30eb__x30c0__x30fc_": clean_value(ビルダー),
                                "_x6848__x4ef6__x540d_": clean_value(案件名),
                                "_x533a__x5206_": clean_value(区分),
                                "_x7279__x8a18__x4e8b__x9805_": clean_value(特記事項),
                                "_x7d0d__x54c1__x65e5_": clean_value(納品日),
                                "_x5de5__x5834_": clean_value(工場),
                            },
                        ):
                            break
                        time.sleep(0.5)
                    while True:
                        if api.write(
                            site_id=DataTochigi_SiteID,
                            drive_id=DataTochigi_DriveID,
                            item_id=DataTochigi_ItemID,
                            range=f"K{upload_file_index+2}",
                            data=[["TRUE"]],
                        ):
                            break
                        time.sleep(0.5)

            # Xử lí từng dòng
            while True:
                api.download_item(
                    site_id=UP.get("id"),
                    breadcrumb=f"データUP一覧/{os.path.basename(DataTochigi)}",
                    save_to=os.path.abspath(DataTochigi),
                )
                data = pd.read_excel(os.path.abspath(DataTochigi))
                if data["Note"].notna().all() and (~data["Note"].str.contains("Đang xử lí")).all():
                    break
                for upload_file_index, row in data.iterrows():
                    if pd.notna(row["Note"]):
                        continue
                    # ---- Các công trình cần bỏ qua ----
                    if row["案件名　（未アップデータ）"] in [
                        "㈱吉村一建設(ナカザワ美原)",
                        "紀の国住宅㈱",
                        "㈱ヤマカ木材(大日本木材防腐)",
                        "㈱ホーク・ワン",
                        "三光ソフラン株式会社",
                        "ゼロ・コーポレーション",
                        "㈱創建(ナカザワ美原)",
                        "ｼﾉｹﾝﾌﾟﾛﾃﾞｭｰｽ",
                    ]:
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"J{upload_file_index+2}",
                                data=[["Bỏ qua công trình này"]],
                            ):
                                break
                            time.sleep(0.5)
                    # ---- Đánh dấu bot đang xử lí dòng/bài này ----
                    while True:
                        if api.write(
                            site_id=DataTochigi_SiteID,
                            drive_id=DataTochigi_DriveID,
                            item_id=DataTochigi_ItemID,
                            range=f"J{upload_file_index+2}",
                            data=[["Đang xử lí"]],
                        ):
                            break
                        time.sleep(0.5)
                    Title, ビルダー, 案件名, 区分, 特記事項, 納品日, 工場, URL, Floors, _, _ = row[:11]
                    breadcrumb = sp.get_breadcrumb(URL)
                    if breadcrumb is None:
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"J{upload_file_index+2}",
                                data=[["Lỗi link"]],
                            ):
                                break
                            time.sleep(0.5)
                    if breadcrumb[-1].endswith("納材"):
                        while True:
                            if api.write(
                                site_id=DataTochigi_SiteID,
                                drive_id=DataTochigi_DriveID,
                                item_id=DataTochigi_ItemID,
                                range=f"J{upload_file_index+2}",
                                data=[["Tên folder có ghi ngày"]],
                            ):
                                break
                            time.sleep(0.5)
                    action_up: bool = True
                    while True:
                        action_up: bool = True
                        # Check Data
                        site_name = api.get_site_from_url(URL)
                        drives = api.get_drives(site_name)
                        drive_id = None
                        for drive in drives:
                            if drive.get("name") == "ドキュメント" and breadcrumb[0] == "Documents":
                                drive_id = drive.get("id")
                                break
                            if drive.get("name") == breadcrumb[0]:
                                drive_id = drive.get("id")
                                break
                        path = f"{"/".join(breadcrumb[1:])}/★データ"
                        if os.path.exists(os.path.join(temp_dir, f"downloads/{案件名}")):
                            shutil.rmtree(os.path.join(temp_dir, f"downloads/{案件名}"))
                        downloads = api.download_drive(
                            drive_id=drive_id,
                            breadcrumb=path,
                            save_to=os.path.join(temp_dir, 案件名),
                        )
                        counts: list[str] = [filepath for _, filepath, _ in downloads]
                        floors: int = 2 if Floors == "-" else len(Floors.split(","))
                        # ---- Đếm số lượng file #
                        has_pdf = any(f.lower().endswith(".pdf") for f in counts)
                        excel_exts = (".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm")
                        excel_count = sum(1 for f in counts if f.lower().endswith(excel_exts))
                        if not has_pdf or excel_count < floors:
                            while True:
                                if api.write(
                                    site_id=DataTochigi_SiteID,
                                    drive_id=DataTochigi_DriveID,
                                    item_id=DataTochigi_ItemID,
                                    range=f"J{upload_file_index+2}",
                                    data=[["Không đủ data"]],
                                ):
                                    action_up = False
                                    break
                                time.sleep(0.5)
                            break
                        pdf_dir = os.path.join(temp_dir, 案件名, "pdf")
                        excel_dir = os.path.join(temp_dir, 案件名, "excel")
                        os.makedirs(name=pdf_dir, exist_ok=True)
                        os.makedirs(name=excel_dir, exist_ok=True)

                        temp: list[str] = []
                        for _, filepath, _ in downloads:
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
                        with FileLock("macro_tochigi.lock", timeout=300):
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
                            while True:
                                if api.write(
                                    site_id=DataTochigi_SiteID,
                                    drive_id=DataTochigi_DriveID,
                                    item_id=DataTochigi_ItemID,
                                    range=f"J{upload_file_index+2}",
                                    data=[["Lỗi macro"]],
                                ):
                                    action_up = False
                                    break
                                time.sleep(0.5)
                            break
                        # Upload
                        downloads: list[str] = temp
                        while True:
                            up: list[dict] = []
                            for f in os.listdir(pdf_dir):
                                up.append(
                                    api.upload_item(
                                        site_id=Mouka.get("id"),
                                        local_path=os.path.join(pdf_dir, f),
                                        breadcrumb=f"真岡工場　製造データ/{納品日}/{Title}/割付図",
                                    )
                                )
                            for f in os.listdir(excel_dir):
                                up.append(
                                    api.upload_item(
                                        site_id=Mouka.get("id"),
                                        local_path=os.path.join(excel_dir, f),
                                        breadcrumb=f"真岡工場　製造データ/{納品日}/{Title}",
                                    )
                                )
                            if all("error" not in item for item in up):
                                while True:
                                    if api.write(
                                        site_id=DataTochigi_SiteID,
                                        drive_id=DataTochigi_DriveID,
                                        item_id=DataTochigi_ItemID,
                                        range=f"J{upload_file_index+2}",
                                        data=[["Chưa có trên Power App"]],
                                    ):
                                        break
                                    time.sleep(0.5)
                                break

                        suffix = f"{month}-{day}納材"
                        sp.rename_breadcrumb(
                            URL,
                            f"{breadcrumb[-1]} {suffix}",
                        )
                        break
                    if action_up:
                        if pa.up(
                            process_date=納品日,
                            factory=工場,
                            build=案件名,
                        ):
                            while True:
                                if api.write(
                                    site_id=DataTochigi_SiteID,
                                    drive_id=DataTochigi_DriveID,
                                    item_id=DataTochigi_ItemID,
                                    range=f"J{upload_file_index+2}",
                                    data=[["OK"]],
                                ):
                                    break
                                time.sleep(0.5)
                    break

            time.sleep(2.5)
