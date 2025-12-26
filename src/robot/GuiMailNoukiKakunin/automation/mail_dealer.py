import time
from contextlib import suppress

from playwright._impl._errors import TimeoutError
from playwright.sync_api import sync_playwright


class MailDealer:
    def __init__(
        self,
        domain: str,
        username: str,
        password: str,
        context=None,
        browser=None,
        playwright=None,
        log_name: str = "MailDealer",
        headless: bool = False,
        timeout: float = 5000,
    ):
        self._external_context = context is not None
        self._external_browser = browser is not None
        self._external_pw = playwright is not None
        self.timeout = timeout
        if playwright:
            self._pw = playwright
        else:
            self._pw = sync_playwright().start()

        if browser:
            self.browser = browser
        else:
            self.browser = self._pw.chromium.launch(
                headless=headless,
                timeout=self.timeout,
                args=["--start-maximized"],
            )

        if context:
            self.context = context
        else:
            self.context = self.browser.new_context(
                no_viewport=True,
            )

        self.page = self.context.new_page()
        self.domain = domain
        self.username = username
        self.password = password
        self.timeout = timeout
        if not self.__authentication():
            raise PermissionError("Authentication failed")

    def __authentication(self) -> bool:
        try:
            self.page.goto(self.domain, wait_until="domcontentloaded")
            self.page.locator(selector="input[id='fUName']").fill(self.username)
            self.page.locator(selector="input[id='fPassword']").fill(self.password)
            with self.page.expect_navigation(
                wait_until="networkidle",
                timeout=30000,
            ):
                self.page.locator(selector="input[type='submit'][value='ログイン']").click()
            with suppress(TimeoutError):
                self.page.wait_for_selector("div[id='md_dialog']", timeout=10000)
                self.page.locator("input[type='button'][id='md_dialog_submit']").click()
            return True
        except TimeoutError:
            return self.__authentication()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self._external_context:
            self.context.close()
        if not self._external_browser:
            self.browser.close()
        if not self._external_pw:
            self._pw.stop()

    def send_mail(
        self,
        fr: str,
        to: str,
        cc: str,
        subject: str,
        body: str,
    ):
        try:
            self.page.bring_to_front()
            self.page.frame(name="side").locator(
                selector="button",
                has=self.page.frame(name="side").locator(
                    selector="span[title='メール作成']",
                ),
            )
            with self.page.expect_popup() as popup:
                self.page.frame(name="side").locator(
                    selector="button", has=self.page.frame(name="side").locator(selector="span", has_text="メール作成")
                ).click()
                page = popup.value
                page.wait_for_function("window.location.href != 'about:blank'")
                page.locator(selector="select[name='fCategoryID'][class='listbox']").select_option(
                    "To/From設定なし(nskhome@nsk-cad.com)"
                )
                page.locator(selector="select[name='fHeaderFooter'][class='listbox']").select_option("署名なし")
                with page.expect_navigation(
                    wait_until="domcontentloaded",
                    timeout=10000,
                ):
                    page.locator("button[class='accent-btn__btn']", has_text="次へ").last.click()
                # Edit From
                page.wait_for_selector("input[name='fFrom']", state="visible").fill(fr)
                time.sleep(0.25)
                # Edit To
                page.wait_for_selector("input[name='fTo[]']", state="visible").fill(to)
                time.sleep(0.25)
                # Edit CC
                if cc:
                    page.wait_for_selector("input[name='fCc[]']", state="visible").fill(cc)
                    time.sleep(0.25)
                # Edit Subject
                page.wait_for_selector("input[id='fSubject']", state="visible").fill(subject)
                time.sleep(0.25)
                # Edit Body
                page.wait_for_selector("textarea[id='fBody']", state="visible").fill(body)
                time.sleep(0.5)
                # Save Temp
                with page.expect_navigation(wait_until="domcontentloaded"):
                    page.locator("button[type='button'][class='accent-btn__btn']", has_text="送信確認").last.click()
                    page.locator("button", has_text="送信 ").first.click()
                    time.sleep(2.5)
                page.close()
                return True
        except TimeoutError:
            return self.send_mail(fr, to, cc, subject, body)

    def associate(self, object_name: str, fMatterID: str):
        try:
            self.page.bring_to_front()
            self.page.locator("input[name='fDQuery[B]']").fill(object_name)
            self.page.locator("button[title='検索']").click()
            self.page.wait_for_selector("div[class='loader']", state="visible", timeout=10000)
            self.page.wait_for_selector("div[class='loader']", state="hidden", timeout=30000)
            # ---- #
            main_iframe = self.page.frame(name="main")
            table = main_iframe.locator("table[id='normalMail']")
            mails = table.locator("tr")
            for i in range(mails.count()):
                mail = mails.nth(i)
                if mail.locator("td[title]").count() == 0:
                    continue
                mail.locator("td[title]").click()
                time.sleep(1)
                break
            main_iframe.locator("button[title='一括操作']").click()
            main_iframe.locator("div[class='pop-panel__content'] input[id='fMatterID_add']").fill(fMatterID)
            main_iframe.locator(
                "div[class='pop-panel__content'] input[name='fAddMatterRelByMGID'] + div.checkbox__indicator"
            ).check()
            main_iframe.locator(
                "div[class='pop-panel__content'] input[id='fMatterID_add'] + button", has_text="関連付ける"
            ).click()
            time.sleep(2.5)
            return True
        except TimeoutError:
            notification = main_iframe.locator("div[class^='mailList-no-tab']").text_content().strip()
            if notification == "検索条件に一致するデータがありません。":
                return notification
            return self.associate(object_name, fMatterID)
