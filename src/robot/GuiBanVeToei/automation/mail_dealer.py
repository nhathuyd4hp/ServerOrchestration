from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright


class MailDealer:
    def __init__(
        self,
        username: str,
        password: str,
        playwright: Playwright,
        browser: Browser,
        context: BrowserContext,
        domain: str = "https://mds3310.maildealer.jp/",
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
            self.page.locator("input[id='fUName']").fill(self.username)
            self.page.locator("input[id='fPassword']").fill(self.password)
            with self.page.expect_navigation(wait_until="load"):
                self.page.locator("input[value='ログイン']").click()
            self.page.locator(selector=f"span[title='{self.username}']").click(timeout=10000)
            return True
        except TimeoutError as e:
            error = self.page.locator("div[id='d_messages']")
            if error.count() == 1 and error.text_content().strip() == "ユーザIDまたはパスワードに誤りがあります。":
                raise PermissionError(error.text_content().strip()) from e
            return self.login()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def send_mail(
        self,
        to: str,
        subject: str,
        nouki: str,
        file: str,
    ) -> bool:
        try:
            self.page.bring_to_front()
            self.page.frame(name="side")
            self.page.frame(name="side").locator("div[class='menu']").click()
            with self.page.expect_popup() as expect:
                self.page.frame(name="side").locator("button[type='button'] > div", has_text="メール作成").click()
                popup = expect.value
                popup.locator("button[class='accent-btn__btn']").first.click()
                popup.locator("input[name='fFrom']").fill("ighd@nsk-cad.com")
                # popup.locator("input[name='fTo[]']").fill(to)
                popup.locator("input[name='fSubject']").fill(subject)
                iframe = popup.wait_for_selector("iframe")
                iframe = iframe.content_frame()
                iframe.locator("body[contenteditable='true']").clear()
                iframe.locator("body[contenteditable='true']").fill(
                    f"""ご担当者様

お世話になっております。
表題の軽天図送付致します。
{nouki} 納品
よろしくお願いいたします。


*エヌ・エス・ケー工業　SDGｓ宣言
***************************************
エヌエスケー工業㈱　
TEL:06-4808-4081
FAX:06-4808-4082
営業時間：9:00～18:00
休日:日曜・祝日

https://www.nsk-cad.com/
***************************************
"""
                )
                popup.locator("div[id='mailBoxAttachBox'] input[type='file']").set_input_files(file)
                # popup.locator("button",has_text="一時保存").click()
                popup.close()
                return True
        except TimeoutError:
            return self.send_mail(to, subject, nouki, file)
