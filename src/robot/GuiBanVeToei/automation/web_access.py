import os
import time
from urllib.parse import urljoin

import pandas as pd
from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright


class WebAccess:
    def __init__(
        self,
        username: str,
        password: str,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
    ):
        self.domain = "https://webaccess.nsk-cad.com/"
        self.username = username
        self.password = password
        self.context = context
        self.playwright = playwright
        self.context = context
        self.browser = browser

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def login(self):
        try:
            self.page = self.context.new_page()
            self.page.goto(self.domain)
            self.page.locator("input[type='text']").fill(self.username)
            self.page.locator("input[type='password']").fill(self.password)
            self.page.locator("button[type='submit']").click()
            self.page.locator("div[id='f-menus'] > div[class='name']").text_content()
        except TimeoutError as e:
            error_message: str = self.page.locator("div[id='f-error-box'] div[class='data']").text_content()
            raise Exception(error_message) from e

    def mail_address(self, case: str) -> str | None:
        try:
            self.page.bring_to_front()
            self.page.locator("a[class='fa fa-industry']").click()
            self.page.locator("button[class='search fa fa-eraser']").click()
            #
            self.page.locator("input[name='search_project_cd']").fill(case)
            with self.page.expect_navigation(wait_until="domcontentloaded"):
                self.page.locator("button[class='search fa fa-search']").click(force=True)
            time.sleep(2.5)
            detailButton = self.page.locator("table input[type='button'][value='参照']")
            if detailButton.count() == 0:
                return None
            detailLinks = list(
                set([detailButton.nth(i).get_attribute("onclick").split("/")[-1] for i in range(detailButton.count())])
            )
            if len(detailLinks) != 1:
                return None
            detailLink = detailLinks[0]
            urljoin(self.domain, detailLink)
            self.page.goto(urljoin(self.domain, detailLink))
            time.sleep(2.5)
            mail_address = self.page.locator("input[id='builder_person_2_mail_addr']").get_attribute("value")
            if mail_address == "":
                return None
            return mail_address

        except TimeoutError:
            return self.mail_address(case)

    def download_data(
        self,
        from_date: str,
        to_date: str,
    ) -> pd.DataFrame:
        try:
            self.page.bring_to_front()
            self.page.locator("a[class='fa fa-industry']").click()
            self.page.locator("button[class='search fa fa-eraser']").click()
            # Lọc theo công trình
            self.page.locator("input[name='search_builder_name_like']").fill("東栄住宅")
            # Theo ngày
            self.page.locator("input[name='search_fix_deliver_date_from']").fill(from_date)
            self.page.locator("input[name='search_fix_deliver_date_to']").fill(to_date)
            # Theo trạng thái
            self.page.locator("button[id='search_drawing_type_ms']").click()
            for drawing in ["作図済", "CBUP済"]:
                self.page.locator(
                    "label[for^='ui-multiselect-5-search_drawing_type-']",
                    has=self.page.locator("span", has_text=drawing),
                ).first.click()
                time.sleep(0.5)
            self.page.locator("button[id='search_drawing_type_ms']").click()
            # Theo trạng thái
            self.page.locator("button[id='search_deliver_type_ms']").click()
            for deliver in ["新規"]:
                self.page.locator(
                    "label[for^='ui-multiselect-3-search_deliver_type-']",
                    has=self.page.locator("span", has_text=deliver),
                ).first.click()
                time.sleep(0.5)
            self.page.locator("button[id='search_deliver_type_ms']").click()
            with self.page.expect_navigation(wait_until="domcontentloaded"):
                self.page.locator("button[class='search fa fa-search']").click(force=True)
            with self.page.expect_download() as download_info:
                self.page.locator("a[class='button fa fa-download']").first.click()
                download = download_info.value
                save_path = os.path.abspath(download.suggested_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                download.save_as(save_path)
                orders = pd.read_csv(save_path, encoding="cp932")
                os.remove(save_path)
                return orders
        except TimeoutError:
            return self.download_data(from_date, to_date)

    def update_state(self, case: str, current_state: str) -> bool:
        try:
            self.page.bring_to_front()
            self.page.bring_to_front()
            self.page.locator("a[class='fa fa-industry']").click()
            self.page.locator("button[class='search fa fa-eraser']").click()
            #
            self.page.locator("input[name='search_project_cd']").fill(case)
            with self.page.expect_navigation(wait_until="domcontentloaded"):
                self.page.locator("button[class='search fa fa-search']").click(force=True)
            time.sleep(2.5)
            detailButton = self.page.locator("table input[type='button'][value='参照']")
            if detailButton.count() == 0:
                return None
            detailLinks = list(
                set([detailButton.nth(i).get_attribute("onclick").split("/")[-1] for i in range(detailButton.count())])
            )
            if len(detailLinks) != 1:
                return None
            detailLink = detailLinks[0]
            urljoin(self.domain, detailLink)
            self.page.goto(urljoin(self.domain, detailLink))
            if current_state == "作図済":
                self.page.locator("select[id='project_drawing']").select_option("送付済")
            elif current_state == "CBUP済":
                self.page.locator("select[id='project_drawing']").select_option("CB送付済")
            else:
                return False
            self.page.locator("button[id='order_update']").first.click()
            time.sleep(5)
            return True
        except TimeoutError:
            return self.update_state(current_state)
