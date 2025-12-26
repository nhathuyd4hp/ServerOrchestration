import os
import tempfile
from datetime import datetime

import pandas as pd
import redis
from celery import shared_task
from playwright.sync_api import sync_playwright

from src.core.config import settings
from src.core.logger import Log
from src.core.redis import REDIS_POOL
from src.robot.GuiMailNoukiKakunin.api import APISharePoint
from src.robot.GuiMailNoukiKakunin.automation import MailDealer
from src.service import ResultService as minio


@shared_task(bind=True, name="Gửi Mail Nouki Kakunin")
def main(self):
    logger = Log.get_logger(channel=self.request.id, redis_client=redis.Redis(connection_pool=REDIS_POOL))
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download
        sapi = APISharePoint(
            TENANT_ID=settings.API_SHAREPOINT_TENANT_ID,
            CLIENT_ID=settings.API_SHAREPOINT_CLIENT_ID,
            CLIENT_SECRET=settings.API_SHAREPOINT_CLIENT_SECRET,
        )
        database_path = sapi.download_item(
            site_id="nskkogyo.sharepoint.com,f8711c8d-9046-4e1c-9de9-e720d1c0c797,90e7b19b-ba14-4986-9e05-cbc7e7358c90",
            breadcrumb="RPA/納期確認送付【横浜】.xlsx",
            save_to=temp_dir,
        )
        database = pd.read_excel(
            io=database_path,
            sheet_name="メール",
        )
    database = database[
        (pd.notna(database["案件番号"])) & (pd.notna(database["得意先名"])) & (pd.notna(database["物件名"]))
    ]
    database["CC先"] = database["CC先"].replace(0, pd.NA)
    database["確定納期"] = pd.to_datetime(database["確定納期"], unit="d", origin="1899-12-30")
    database["確定納期"] = database["確定納期"].apply(lambda x: f"{x.month}月{x.day}日" if pd.notna(x) else pd.NA)

    database.to_excel(database_path, index=False, sheet_name="メール")

    database = pd.read_excel(
        io=database_path,
        sheet_name="メール",
        dtype={
            "案件番号": int,
        },
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--start-maximized",
            ],
        )
        context = browser.new_context(no_viewport=True)
        with MailDealer(
            domain="https://mds3310.maildealer.jp/",
            username="vietnamrpa",
            password="nsk159753",
            playwright=p,
            browser=browser,
            context=context,
        ) as md:
            for index, row in database.iterrows():
                logger.info(f"{index+1} - {row['案件番号']} - {row['得意先名']} - {row['物件名']}")
                fr = row["FROM先"]
                to = row["TO先"]
                cc = None if pd.isna(row["CC先"]) else row["CC先"]
                if not (fr and to):
                    database.at[index, "結果"] = False
                    continue
                send_mail = False
                if row["不足"] == "なし":
                    send_mail = md.send_mail(
                        fr=fr,
                        to=to,
                        cc=cc,
                        subject=f"{row['物件名']} 納期確認【※ご案内とご注意事項ご確認下さい】",
                        body=f"""{row['担当者']}様


いつも大変お世話になっております。
ご依頼頂いております、軽天材の納材日確認となります。


【納材日：{row['確定納期']}】


変更等御座いましたら、５日(営業日)前までに
ご連絡をお願い致します。

※納材日2日前(2営業日前)以降の納期変更に関しては別途費用を頂戴しております。
ご注意の上、納期をご確認下さい。



──────＜ご案内とご注意事項＞──────
▼中入れについて
建物内への納材はお受けしておりません。
予めご了承のほど宜しくお願い致します。

▼納材場所の確保について
本メールが届きましたら、納材場所をご検討いただき、
当日、大工さん不在の際は納材場所の確保をお願い致します。
───────────────────────

ご連絡の行違いが御座いましたら、
お詫び申し上げます。
よろしくお願い致します。
───────────────────────

　エヌ・エス・ケー工業株式会社　横浜営業所　トー

　〒222-0033
　横浜市港北区新横浜２－４－６　マスニ第一ビル８F
　TEL:(045)595-9165　FAX:(045)577-0012
　営業時間：9:00～18:00
　休日:日曜・祝日
-----・・・・・----------・・・・・----------・・・・・-----
""",
                    )
                else:
                    send_mail = md.send_mail(
                        fr=fr,
                        to=to,
                        cc=cc,
                        subject=f"{row['物件名']} 納期確認【※ご案内とご注意事項ご確認下さい】【※不足資料あり】",
                        body=f"""{row['担当者']}様


いつも大変お世話になっております。
ご依頼頂いております、軽天材の納材日確認となります。


【納材日：{row['確定納期']}】


★{row['不足']}が不足しておりますので、大至急送付をお願い致します。

変更等御座いましたら、５日(営業日)前までに
ご連絡をお願い致します。

※納材日2日前(2営業日前)以降の納期変更に関しては別途費用を頂戴しております。
ご注意の上、納期をご確認下さい



──────＜ご案内とご注意事項＞──────
▼中入れについて
建物内への納材はお受けしておりません。
予めご了承のほど宜しくお願い致します。

▼納材場所の確保について
本メールが届きましたら、納材場所をご検討いただき、
当日、大工さん不在の際は納材場所の確保をお願い致します。
───────────────────────

また、ご連絡の行違いが御座いましたら、
お詫び申し上げます。

※年末年始休業期間のお知らせ※
------------------------------------------
 2025年12月27日(土)　～　2026年01月04日(日)
------------------------------------------
営業は2026年1月5日（月）の午前9時より再開いたします。 年末年始休業中のお問い合わせにつきましては、休業期間後の回答とさせていただきます。
ご不便をおかけしますが何卒ご了承くださいますようお願い申し上げます。


----・・・・・----------・・・・・----------・・・・・-----

　エヌ・エス・ケー工業株式会社　横浜営業所　トー

　〒222-0033
　横浜市港北区新横浜２－４－６　マスニ第一ビル８F
　TEL:(045)595-9165　FAX:(045)577-0012
　営業時間：9:00～18:00
　休日:日曜・祝日
-----・・・・・----------・・・・・----------・・・・・-----
""",
                    )
                if not send_mail:
                    database.at[index, "結果"] = send_mail
                    continue
                database.at[index, "結果"] = md.associate(
                    object_name=row["物件名"],
                    fMatterID=str(row["案件番号"]),
                )
            with tempfile.TemporaryDirectory() as temp_dir:
                today_str = datetime.now().strftime("%Y-%m-%d")
                ResultFile = f"Result_{today_str}.xlsx"
                temp_file_path = os.path.join(temp_dir, ResultFile)
                database.to_excel(temp_file_path, index=False)
                result = minio.fput_object(
                    bucket_name=settings.MINIO_BUCKET,
                    object_name=f"GuiMailNoukiKakunin/{ResultFile}",
                    file_path=temp_file_path,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                return result.object_name
