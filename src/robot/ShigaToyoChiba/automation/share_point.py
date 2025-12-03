import os
import re
from typing import List
from urllib.parse import urlparse

from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright


class SharePoint:
    def __init__(
        self,
        domain: str,
        username: str,
        password: str,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
    ):
        self.domain = domain
        self.username = username
        self.password = password
        self.context = context
        self.playwright = playwright
        self.context = context
        self.browser = browser

    def login(self) -> bool:
        try:
            self.page = self.context.new_page()
            self.page.bring_to_front()
            self.page.goto(self.domain, wait_until="domcontentloaded")
            if urlparse(self.page.url).netloc != urlparse(self.domain).netloc:
                try:
                    self.page.locator("input[type='email']").fill(self.username)
                    self.page.locator(
                        selector="input[type='submit']",
                        has_text="Next",
                    ).click()
                    self.page.locator("input[type='password']").fill(self.password)
                    self.page.locator(
                        selector="input[type='submit']",
                        has_text="Sign in",
                    ).click()
                    with self.page.expect_navigation(
                        url=re.compile(f"^{self.domain}"),
                        wait_until="load",
                        timeout=30000,
                    ):
                        self.page.locator("input[type='submit']", has_text="Yes").click()
                except TimeoutError:
                    return False
            while True:
                try:
                    self.page.wait_for_selector("div[id='HeaderButtonRegion']", state="visible", timeout=10000)
                    self.page.locator(selector="div[id='O365_MainLink_MePhoto']").click()
                    break
                except TimeoutError:
                    self.page.reload(wait_until="domcontentloaded")
            return True
        except TimeoutError:
            return self.login()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def download(
        self,
        url: str,
        file: re.Pattern | str,
        steps: List[str | re.Pattern] | None = None,
        save_to: str | None = None,
    ) -> List[str]:
        try:
            self.page.bring_to_front()
            downloads = []
            self.page.goto(url=url)
            self.page.wait_for_selector(
                selector="div[class='app-container']",
                timeout=10000,
                state="visible",
            )
            for step in steps or []:
                span = self.page.locator(
                    selector="span[role='button']",
                    has_text=step,
                )
                try:
                    span.first.wait_for(state="visible", timeout=5000)
                except TimeoutError:
                    return []
                if span.count() != 1:
                    return []
                text = span.text_content()
                span.click()
                self.page.locator(
                    selector="div[type='button'][data-automationid='breadcrumb-crumb']:visible",
                    has_text=text,
                ).wait_for(
                    state="visible",
                )
            self.page.locator(
                selector="span[role='button'][data-id='heroField']",
                has_text=file,
            ).first.wait_for(timeout=5000, state="visible")
            items = self.page.locator(
                selector="span[role='button'][data-id='heroField']",
                has_text=file,
            )
            for i in range(items.count()):
                item = items.nth(i)
                item.click(button="right")
                download_btn = self.page.locator(
                    "button[data-automationid='downloadCommand'][role='menuitem']:not([type='button'])"
                )
                download_btn.wait_for(state="visible")
                with self.page.expect_download() as download_info:
                    download_btn.click()
                download = download_info.value
                if save_to:
                    save_path = os.path.join(save_to, download.suggested_filename)
                else:
                    save_path = os.path.abspath(download.suggested_filename)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                download.save_as(save_path)
                downloads.append(save_path)
            return downloads
        except TimeoutError:
            if self.page.locator("div[id='ms-error-content']").count() == 1:
                notification: str = (
                    self.page.locator("div[id='ms-error-content']").text_content().strip().split("\n")[0]
                )
                if (
                    notification
                    == "このドキュメントにアクセスできません。このドキュメントを共有するユーザーに連絡してください。"
                ):
                    return []
            return self.download(url, file, steps, save_to)

    def upload(
        self,
        url: str,
        files: List[str],
        steps: List[str | re.Pattern] | None = None,
    ) -> bool:
        try:
            self.page.bring_to_front()
            self.page.goto(url=url)
            for step in steps or []:
                span = self.page.locator(
                    selector="span[role='button']",
                    has_text=step,
                )
                try:
                    span.first.wait_for(state="visible", timeout=5000)
                except TimeoutError:
                    return False
                if span.count() != 1:
                    return False
                text = span.text_content()
                span.click()
                self.page.locator(
                    selector="div[type='button'][data-automationid='breadcrumb-crumb']:visible",
                    has_text=text,
                ).wait_for(
                    state="visible",
                )
            pass
        except TimeoutError:
            return self.upload(url, files, steps)

    def get_breadcrumb(self, url: str) -> List[str]:
        try:
            self.page.bring_to_front()
            self.page.goto(url)
            self.page.locator("li[data-automationid='breadcrumb-listitem']:visible").first.wait_for(state="visible")
            return [
                self.page.locator("li[data-automationid='breadcrumb-listitem']:visible").nth(i).text_content()
                for i in range(self.page.locator("li[data-automationid='breadcrumb-listitem']:visible").count())
            ]
        except TimeoutError:
            return self.get_breadcrumb(url)
