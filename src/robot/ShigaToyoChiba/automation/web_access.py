import os
from datetime import date

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
        self.page = self.context.new_page()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def login(self):
        try:
            self.page.goto(self.domain)
            self.page.locator("input[type='text']").fill(self.username)
            self.page.locator("input[type='password']").fill(self.password)
            self.page.locator("button[type='submit']").click()
            self.page.locator("div[id='f-menus'] > div[class='name']").text_content()
        except TimeoutError as e:
            error_message: str = self.page.locator("div[id='f-error-box'] div[class='data']").text_content()
            raise Exception(error_message) from e

    def download_data(self, process_date: date):
        try:
            self.page.bring_to_front()
            self.page.locator("a[class='fa fa-industry']").click()
            self.page.locator("button[class='search fa fa-eraser']").click()
            #
            self.page.locator("input[name='search_fix_deliver_date_from']").fill(process_date.strftime("%Y/%m/%d"))
            self.page.locator("input[name='search_fix_deliver_date_to']").fill(process_date.strftime("%Y/%m/%d"))
            #
            self.page.locator("button[id='multi_factory_cd_ms']").click()
            for factory in ["滋賀", "豊橋", "千葉"]:
                self.page.locator(
                    "label[for^='ui-multiselect-1-multi_factory_cd-']",
                    has=self.page.locator(
                        "span",
                        has_text=factory,
                    ),
                ).check()
            self.page.locator("button[id='multi_factory_cd_ms']").click()
            #
            self.page.locator("button[id='search_deliver_type_ms']").click()
            for ship in ["新規", "引揚"]:
                self.page.locator(
                    "label[for^='ui-multiselect-3-search_deliver_type-']",
                    has=self.page.locator(
                        "span",
                        has_text=ship,
                    ),
                ).check()
            self.page.locator("button[id='search_deliver_type_ms']").click()
            #
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
            return self.download_data(process_date)
