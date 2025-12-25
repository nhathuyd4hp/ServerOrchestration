import time
from contextlib import suppress

from playwright._impl._errors import TimeoutError
from playwright.sync_api import Browser, BrowserContext, Playwright


class AndPad:
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
            self.page.goto(self.domain, wait_until="networkidle")
            with self.page.expect_navigation(wait_until="domcontentloaded"):
                self.page.locator("input[value='ログイン画面へ']").click()
            self.page.locator("input[id='email']").fill(self.username)
            self.page.locator("input[id='password']").fill(self.password)
            time.sleep(1)
            with self.page.expect_navigation(wait_until="networkidle"):
                self.page.locator("button[id='btn-login']").click()
            self.page.locator("span", has_text="ログアウト").wait_for(timeout=10000, state="visible")
            return True
        except TimeoutError:
            if self.page.locator("p[id='error-message-login-failed-text']").count() == 1:
                return False
            return self.__authentication()

    def __enter__(self):
        if not self.login():
            raise PermissionError("authentication failure")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            self.browser.close()

    def send_message(
        self, object_name: str, message: str, tags: list[str] | None = None, attachments: list[str] | None = None
    ):
        try:
            self.page.bring_to_front()
            with self.page.expect_navigation(wait_until="networkidle"):
                self.page.goto(self.domain)
            textbox = self.page.locator("input[class='search__textbox']")
            textbox.fill(object_name)
            with self.page.expect_navigation(wait_until="networkidle"):
                textbox.press("Enter")
            self.page.wait_for_selector("table[class='table']", state="visible")
            if self.page.locator("table[class='table'] > tbody > tr").count() != 1:
                return "Không tìm thấy công trình ở AndPad"
            with self.page.expect_navigation(wait_until="networkidle"):
                self.page.locator("table[class='table'] > tbody > tr").click()
            # Kiểm tra đã gửi tin nhắn chưa
            with self.page.expect_popup() as popup:
                self.page.locator("a", has_text="チャット").last.click()
                popup = popup.value
                with suppress(TimeoutError):
                    popup.wait_for_load_state(state="networkidle", timeout=10000)
                count_message = popup.locator("p[class='chat-message-text']").count()
                list_message = [
                    popup.locator("p[class='chat-message-text']").nth(i).text_content() for i in range(count_message)
                ]
                if any(repr(msg.strip()) == repr(message.strip()) for msg in list_message):
                    popup.close()
                    return "Tin nhắn đã được gửi trước đó"
                message_box = popup.wait_for_selector("textarea[placeholder='メッセージを入力']", state="visible")
                message_box.fill("")
                message_box.fill(message)
                # Clear tag
                time.sleep(1)
                while True:
                    if popup.locator("span[class='label-chat-to__delete']:visible").count() == 0:
                        break
                    popup.locator("span[class='label-chat-to__delete']:visible").nth(0).click()
                    time.sleep(1)
                if tags:
                    for tag in tags:
                        popup.locator("button", has=popup.locator("span", has_text="お知らせ")).click()
                        time.sleep(1.5)
                        popup.locator("input[placeholder='氏名で絞込']").fill(tag)
                        time.sleep(1.5)
                        notify_list = popup.locator("label[data-test='notify-member-cell']")
                        if notify_list.count() != 1:
                            return "Lỗi tag: không xác định"
                        if not popup.locator(
                            "label[data-test='notify-member-cell'] > input[type='checkbox']"
                        ).is_checked():
                            popup.locator("label[data-test='notify-member-cell'] > input[type='checkbox']").click()
                        popup.locator(selector="wc-tsukuri-text", has_text="選択").click()
                        time.sleep(0.5)
                    if popup.locator("span[class='chat-to__label']:visible").count() != 3:
                        popup.close()
                        return self.send_message(object_name, message)
                time.sleep(1)
                # Click
                popup.locator(selector="wc-tsukuri-text", has_text="送信").click()
                time.sleep(4.5)
                popup.locator("input[type='file'][data-test='input-document']").set_input_files(attachments)
                time.sleep(4.5)
                popup.close()
                return True
        except TimeoutError:
            return self.send_message(object_name, message)
        except Exception as e:
            return f"Lỗi {e}"
