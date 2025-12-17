import re
import time

from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright


class PowerApp:
    def __init__(
        self,
        username: str,
        password: str,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        domain: str = "https://apps.powerapps.com/play/e/default-3255306b-4eff-41c9-89fb-3e24e65f48a1/a/f1e99b17-afcd-4d42-9af3-c4f9ee79469d?tenantId=3255306b-4eff-41c9-89fb-3e24e65f48a1",
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
            self.page.frame_locator("iframe[class='player-app-frame']").locator(
                "input[appmagic-control='idtextbox']"
            ).fill(self.username)
            self.page.frame_locator("iframe[class='player-app-frame']").locator(
                "input[appmagic-control='pwtextbox']"
            ).fill(self.password)
            self.page.frame_locator("iframe[class='player-app-frame']").locator("button", has_text="Login").click()
            try:
                self.page.frame_locator("iframe[class='player-app-frame']").locator(
                    "button", has_text="Login"
                ).wait_for(timeout=15000, state="detached")
                return True
            except TimeoutError as e:
                raise PermissionError("PowerApp - PermissionError") from e
        except TimeoutError:
            return self.login()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def up(
        self,
        process_date: str,
        factory: str,
        build: str,
    ) -> bool:
        try:
            self.page.bring_to_front()
            for i in range(0, 2):
                dropdown = (
                    self.page.frame_locator("iframe[class='player-app-frame']")
                    .locator("div[aria-haspopup='listbox']")
                    .nth(i)
                )
                while True:
                    if dropdown.get_attribute("aria-expanded") == "true":
                        time.sleep(1 / 3)
                        break
                    dropdown.click()
                    time.sleep(1 / 3)
                time.sleep(1 / 3)
                for j in range(
                    self.page.frame_locator("iframe[class='player-app-frame']").locator("div[role='option']").count()
                ):
                    option = (
                        self.page.frame_locator("iframe[class='player-app-frame']").locator("div[role='option']").nth(j)
                    )
                    if option.text_content() in [process_date, factory] and option.is_visible():
                        option.click()
                        time.sleep(1 / 3)
                        break
            self.page.frame_locator("iframe[class='player-app-frame']").locator("input[placeholder='案件検索']").clear()
            time.sleep(1 / 3)
            self.page.frame_locator("iframe[class='player-app-frame']").locator("input[placeholder='案件検索']").fill(
                build
            )
            time.sleep(2 / 3)
            if self.page.frame_locator("iframe[class='player-app-frame']").locator("div[role='listitem']").count() != 1:
                return False
            content = (
                self.page.frame_locator("iframe[class='player-app-frame']")
                .locator("div[role='listitem']")
                .text_content()
                .replace("\n", " ")
                .strip()
            )
            if process_date in content and build in content:
                while True:
                    if (
                        "UP済"
                        in self.page.frame_locator("iframe[class='player-app-frame']")
                        .locator("div[role='listitem']")
                        .text_content()
                        .replace("\n", " ")
                        .strip()
                    ):
                        return True
                    self.page.frame_locator("iframe[class='player-app-frame']").locator(
                        "div[role='listitem'] div[id^='react-combobox-view']:visible"
                    ).click()
                    self.page.frame_locator("iframe[class='player-app-frame']").locator(
                        "span:visible", has_text=re.compile("^UP済$")
                    ).click()
                    self.page.frame_locator("iframe[class='player-app-frame']").locator(
                        "div:visible", has_text=re.compile("^YES$")
                    ).click()
                    time.sleep(1)
            else:
                return False
        except TimeoutError:
            try:
                self.page.frame_locator("iframe[class='player-app-frame']").locator(
                    "div:visible", has_text=re.compile("^NO$")
                ).click(timeout=5000)
            except TimeoutError:
                pass
            return self.up(process_date, factory, build)
