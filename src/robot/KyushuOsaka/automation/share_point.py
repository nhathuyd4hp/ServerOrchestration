import os
import re
import time
from typing import List

from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright
from pywinauto import Application, findwindows


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
        self.page = self.context.new_page()

    def login(self) -> bool:
        try:
            self.page.bring_to_front()
            self.page.goto(self.domain, wait_until="domcontentloaded")
            self.page.locator("input[type='email']").fill(self.username)
            self.page.locator(
                selector="input[type='submit']",
                has_text="Next",
            ).click()
            time.sleep(1)
            self.page.locator("input[type='password']").fill(self.password)
            self.page.locator(
                selector="input[type='submit']",
                has_text="Sign in",
            ).click()
            time.sleep(1)
            with self.page.expect_navigation(
                url=re.compile(f"^{self.domain}"),
                wait_until="load",
                timeout=30000,
            ):
                self.page.locator("input[type='submit']", has_text="Yes").click()
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
            while True:
                if (
                    self.page.locator("button[data-automationid='uploadCommand']").get_attribute("aria-expanded")
                    == "true"
                ):
                    self.page.locator("button[data-automationid='uploadFileCommand']").click()
                    time.sleep(0.5)
                    if self.page.locator("input[type='file']").count() == 1:
                        break
                self.page.locator("button[data-automationid='uploadCommand']").click()
                time.sleep(0.5)
            self.page.locator("input[type='file']").set_input_files(files)
            self.page.wait_for_selector(
                "div[class^='toastInnerContainer-'] i[data-icon-name='Cancel']", state="visible", timeout=30000
            )
            time.sleep(0.25)
            while True:
                if windows := findwindows.find_windows(title="Open"):
                    for window in windows:
                        app = Application().connect(handle=window)
                        dlg = app.window(handle=window)
                        dlg.child_window(title="Cancel", class_name="Button").click()
                    if findwindows.find_windows(title_re="Open"):
                        continue
                    else:
                        break
                time.sleep(0.25)
            return True
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

    def rename_breadcrumb(self, url: str, new_name: str) -> bool:
        try:
            self.page.bring_to_front()
            self.page.goto(url)
            self.page.locator("i[name='OpenPane']").click()
            self.page.frame_locator("iframe[data-automationid='infoPane']").locator(
                "button", has_text="Edit all"
            ).click()
            self.page.frame_locator("iframe[data-automationid='infoPane']").locator("input[type='text']").fill(new_name)
            self.page.frame_locator("iframe[data-automationid='infoPane']").locator(
                "button[data-automationid='ReactClientFormSaveButton']",
                has=self.page.frame_locator("iframe[data-automationid='infoPane']").locator(
                    "span",
                    has_text="Save",
                ),
            ).click()
            self.page.frame_locator("iframe[data-automationid='infoPane']").locator(
                "button", has_text="Edit all"
            ).wait_for(state="attached")
            return True
        except TimeoutError:
            if self.page.frame_locator("iframe[data-automationid='infoPane']").locator(":scope").count() == 0:
                try:
                    self.page.locator("input[type='text']").fill(new_name)
                    time.sleep(0.25)
                    self.page.locator("button[data-automationid='ReactClientFormSaveButton']").click()
                    time.sleep(4.75)
                    return True
                except TimeoutError:
                    return False
            return self.rename_breadcrumb(url, new_name)
