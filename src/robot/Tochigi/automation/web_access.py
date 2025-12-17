import pandas as pd
import os
from datetime import date
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
        domain: str = "https://webaccess.nsk-cad.com/",
    ):
        self.domain = domain
        self.username = username
        self.password = password
        self.context = context
        self.playwright = playwright
        self.context = context
        self.browser = browser
        self.page = self.context.new_page()
        self.login()

    def login(self) -> bool:
        try:
            self.page.bring_to_front()
            self.page.goto(self.domain, wait_until="domcontentloaded")
            self.page.locator("input[type='text']").fill(self.username)
            self.page.locator("input[type='password']").fill(self.password)
            self.page.locator("button[class='btn login']").click()
            self.page.locator("div[id='f-header']").wait_for(state="attached")
            if self.page.locator("div[id='f-error-box']").count():
                raise PermissionError(self.page.locator("div[id='f-error-box']").text_content().strip())
            if self.page.locator("div[id='f-header'] div[id='f-menus']").count():
                return True
        except TimeoutError:
            return self.login()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def download_data(self,process_date: date):
        try:
            self.page.bring_to_front()
            with self.page.expect_navigation(wait_until="domcontentloaded"):
                self.page.locator("a[class='fa fa-industry']").click()
            # Clear
            # Filter
            self.page.locator("input[name='search_fix_deliver_date_from']").fill(str(process_date).replace("-","/"))
            self.page.locator("input[name='search_fix_deliver_date_to']").fill(str(process_date).replace("-","/"))
            while True:
                factory = self.page.locator("button[id='multi_factory_cd_ms']")
                if factory.text_content() == "栃木":
                    break
                factory.click()
                self.page.locator("label[for^='ui-multiselect-1-multi_factory_cd-']",has_text="栃木").check()
                factory.click()
            # Search
            with self.page.expect_navigation(wait_until="networkidle"):
                self.page.locator("button[class='search fa fa-search']").click()
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

    