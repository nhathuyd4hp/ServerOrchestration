import os
import time

import pandas as pd
from playwright._impl._errors import TimeoutError
from playwright.async_api import Browser, BrowserContext, Playwright


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

    def download_data(self, building: str):
        try:
            self.page.bring_to_front()
            self.page.locator("a[class='fa fa-industry']").click()
            self.page.locator("button[class='search fa fa-eraser']").click()

            self.page.locator("input[name='search_builder_name_like']").fill(building)

            self.page.locator("button[id='search_drawing_type_ms']").click()
            for drawing in ["送付済", "CB送付済"]:
                self.page.locator(
                    "label[for^='ui-multiselect-5-search_drawing_type-']",
                    has=self.page.locator("span", has_text=drawing),
                ).first.click()
                time.sleep(0.1)
            self.page.locator("button[id='search_drawing_type_ms']").click()

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
            return self.download_data(building=building)
