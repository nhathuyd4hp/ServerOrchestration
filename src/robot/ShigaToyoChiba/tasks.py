import os
import re
from datetime import date, datetime

import pandas as pd
import xlwings as xw
from celery import shared_task
from filelock import FileLock
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.robot.ShigaToyoChiba.api import APISharePoint
from src.robot.ShigaToyoChiba.automation import SharePoint, WebAccess


@shared_task
def shiga_toyo_chiba(process_date: date | str):
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
        process_date = datetime.strptime(process_date, "%Y/%m/%d").date()
    # ---- File Data
    FileData = f"DataShigaToyoChiba{process_date.strftime("%m-%d")}.xlsx"
    # ---- UP site
    UPSite = APIClient.get_site("UP")
    # ---- Upload File Data
    if not APIClient.download_item(
        site_id=UPSite.get("id"),
        breadcrumb=f"データUP一覧/{FileData}",
        save_to=".",
    ):
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
                orders.to_excel(FileData, index=False)
                # Upload to SharePoint
                item = APIClient.upload_item(
                    site_id=UPSite.get("id"),
                    breadcrumb="データUP一覧",
                    local_path=FileData,
                    replace=False,
                )
                DataShigaUp_ItemID = item.get("id")
                DataShigaUp_DriveID = item.get("parentReference").get("driveId")
                DataShigaUp_SiteID = item.get("parentReference").get("siteId")
    else:
        item = APIClient.upload_item(
            site_id=UPSite.get("id"),
            breadcrumb="データUP一覧",
            local_path=FileData,
            replace=False,
        )
        DataShigaUp_ItemID = item.get("id")
        DataShigaUp_DriveID = item.get("parentReference").get("driveId")
        DataShigaUp_SiteID = item.get("parentReference").get("siteId")
    # ---- Upload Data
    # suffix_name = f"{process_date.strftime("%m-%d")}納材"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        with SharePoint(
            domain=settings.SHAREPOINT_DOMAIN,
            username=settings.SHAREPOINT_EMAIL,
            password=settings.SHAREPOINT_PASSWORD,
            playwright=p,
            browser=browser,
            context=context,
        ) as sp:
            while True:
                APIClient.download_item(
                    site_id=UPSite.get("id"),
                    breadcrumb=f"データUP一覧/{FileData}",
                    save_to=".",
                )
                data = pd.read_excel(FileData)
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
                    APIClient.write(
                        siteId=DataShigaUp_SiteID,
                        driveId=DataShigaUp_DriveID,
                        itemId=DataShigaUp_ItemID,
                        range=f"E{index+2}",
                        data=[["Đang xử lí"]],
                    )
                    # Get breadcrumb
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
                    downloads = sp.download(
                        url=url,
                        file=re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam|pdf)$", re.IGNORECASE),
                        steps=[re.compile("^★データ$")],
                        save_to=f"downloads/ShigaToyoChiba/{row['案件番号']}",
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
                            if re.compile(r".*\.(xls|xlsx|xlsm|xlsb|xml|xlt|xltx|xltm|xlam)$", re.IGNORECASE).match(f)
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
                    # --- Kiểm tra tên file --- #
                    if any(row["物件名"] not in os.path.basename(download) for download in downloads):
                        APIClient.write(
                            siteId=DataShigaUp_SiteID,
                            driveId=DataShigaUp_DriveID,
                            itemId=DataShigaUp_ItemID,
                            range=f"E{index+2}",
                            data=[["Lỗi filename"]],
                        )
                        break
                    # --- Kiểm tra macro
                    try:
                        with FileLock("macro.lock", timeout=300):
                            app = xw.App(visible=False)
                            macro_file = "src/robot/ShigaToyoChiba/resource/マクロチェック(240819ver).xlsm"
                            wb_macro = app.books.open(macro_file)
                            # threading.Thread(target=Fname,args=(excel_folder,)).start()
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
                    if row["出荷工場"] == "滋賀":  # Shiga
                        sp.upload(
                            url="https://nskkogyo.sharepoint.com/sites/shiga/Shared Documents/Forms/AllItems.aspx?id=/sites/shiga/Shared Documents/滋賀工場 製造データ",  # noqa
                            files=downloads,
                            steps=[
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                )
                            ],
                        )
                    elif row["出荷工場"] == "豊橋":  # Toyo
                        sp.upload(
                            url="https://nskkogyo.sharepoint.com/sites/toyohashi/Shared Documents/Forms/AllItems.aspx?id=/sites/toyohashi/Shared Documents/豊橋工場 製造データ",  # noqa
                            files=downloads,
                            steps=[
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                )
                            ],
                        )
                    elif row["出荷工場"] == "千葉":  # Chiba
                        sp.upload(
                            url="https://nskkogyo.sharepoint.com/sites/nskhome/Shared Documents/Forms/AllItems.aspx?id=/sites/nskhome/Shared Documents/千葉工場 製造データ",  # noqa
                            files=downloads,
                            steps=[
                                re.compile(
                                    rf"(?:{process_date.month}|{process_date.month:02d})月(?:{process_date.day}|{process_date.day:02d})日配送分"
                                )
                            ],
                        )
                    else:
                        APIClient.write(
                            siteId=DataShigaUp_SiteID,
                            driveId=DataShigaUp_DriveID,
                            itemId=DataShigaUp_ItemID,
                            range=f"E{index+2}",
                            data=[["Lỗi: kiểm tra cột 出荷工場"]],
                        )
                        break
