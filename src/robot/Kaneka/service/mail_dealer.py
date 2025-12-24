import os
import re
import time

import pandas as pd
from pywinauto.findwindows import ElementNotFoundError
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from src.robot.Kaneka.common.decorator import retry_if_exception
from src.robot.Kaneka.core import IWebDriver, IWebDriverMeta


class WebAccessMeta(IWebDriverMeta):
    def __new__(cls, name: str, bases: tuple, class_dict: dict):
        # Lọc qua tất cả các phương thức của class
        for attr_name, attr_value in class_dict.items():
            # Kiểm tra nếu là hàm (không bao gồm hàm khởi tạo và hàm login)
            if callable(attr_value) and attr_name not in [
                "__init__",
                "_authentication",
            ]:
                class_dict[attr_name] = cls.login(attr_value)
        # Tạo class mới với metaclass này
        return super().__new__(cls, name, bases, class_dict)

    @staticmethod
    def login(func):
        def wrapper(self, *args, **kwargs):
            if not self.authenticated:
                raise Exception("Yêu cầu xác thực")
            if not self.browser.current_url.endswith("/app/") or self.browser.current_url == "data:,":
                self.authenticated = self._authentication(self._username, self._password)
            self.browser.switch_to.default_content()
            result = func(self, *args, **kwargs)
            self.browser.switch_to.default_content()
            return result

        return wrapper


class MailDealer(IWebDriver, metaclass=WebAccessMeta):
    def __init__(self, username: str, password: str, **kwargs):
        super().__init__(**kwargs)
        self.url = "https://mds3310.maildealer.jp/"
        self._username = username
        self._password = password
        self.authenticated = self._authentication(self._username, self._password)
        self.email_to_lastname = {
            "junichiro.kawakatsu@kaneka.co.jp": "川勝",
            "hideaki.takeshiro@kaneka.co.jp": "武城",
            "haruna.kuge@kaneka.co.jp": "久家",
            "shigeru.yokota@kaneka.co.jp": "横田",
            "takafumi.miki@kaneka.co.jp": "三木",
            "chie.nakamura@kaneka.co.jp": "中村",
            "kazuki.masuda1@kaneka.co.jp": "増田",
            "miku.ichinotsubo@kaneka.co.jp": "一ノ坪",
            "yuki.date@kaneka.co.jp": "伊達",
        }
        if not self.authenticated:
            raise Exception("Kiểm tra thông tin xác thực")
        self.logger.info("Xác thực thành công")

    @retry_if_exception(
        exceptions=(
            StaleElementReferenceException,
            ElementClickInterceptedException,
        )
    )
    def _authentication(self, username: str, password: str) -> bool:
        self._navigate(self.url)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='fUName']"))).send_keys(username)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='fPassword']"))).send_keys(password)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))).click()
        time.sleep(self.retry_interval)
        while self.browser.execute_script("return document.readyState") != "complete":
            time.sleep(self.retry_interval)
        try:
            olv_dialog = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class='olv-dialog']")))
            time.sleep(self.retry_interval)
            for button in olv_dialog.find_elements(By.TAG_NAME, "button"):
                if button.text.find("同意する") != -1:
                    self.wait.until(EC.element_to_be_clickable(button)).click()
                    break
        except TimeoutException:
            pass
        return "/app/" in self.browser.current_url

    @retry_if_exception(
        exceptions=(
            ElementClickInterceptedException,
            StaleElementReferenceException,
        )
    )
    def _switch_mail_box(self, mailbox: str) -> bool:
        iframe = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id='ifmSide']")))
        self.browser.switch_to.frame(iframe)
        for button in self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button[class^='olv-p-side-nav__toggle']"))
        ):
            if not button.get_attribute("class").endswith("--is-open"):
                self.wait.until(EC.element_to_be_clickable(button))
                self.browser.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    button,
                )
                button.click()
                time.sleep(self.retry_interval)
                # -- Mailbox
                if self.browser.find_elements(By.CSS_SELECTOR, f"span[title='{mailbox}']"):
                    self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, f"span[title='{mailbox}']"))).click()
                    break
        time.sleep(self.retry_interval)
        spans = self.browser.find_elements(By.CSS_SELECTOR, f"span[title='{mailbox}']")
        if not spans:
            raise Exception(f"Không tìm thấy hộp thư {mailbox}")
        # -- Mailbox -- #
        span = self.browser.find_element(By.CSS_SELECTOR, f"span[title='{mailbox}']")
        self.browser.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", span)
        self.wait.until(EC.element_to_be_clickable(span)).click()
        time.sleep(self.retry_interval)
        return True

    @retry_if_exception(
        exceptions=(
            StaleElementReferenceException,
            ElementClickInterceptedException,
        )
    )
    def mailbox(self, mailbox: str, tab: str | None = "新着") -> pd.DataFrame:
        self.logger.info(f"Đọc MailBox {mailbox}, Tab {tab}")
        if not self._switch_mail_box(mailbox):
            raise Exception(f"Không thể chuyển đến hộp thư {mailbox}")
        iframe = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id='ifmMain']")))
        self.browser.switch_to.frame(iframe)
        # -- Switch Tab -- #
        olv_c_tab__names = self.wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span[class='olv-c-tab__name']"))
        )
        for olv_c_tab__name in olv_c_tab__names:
            if olv_c_tab__name.text == tab:
                pass
                self.wait.until(EC.element_to_be_clickable(olv_c_tab__name)).click()
                break
        time.sleep(self.retry_interval)
        table = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))
        # -- Dataframe -- #
        columns = []
        index_columns = []
        row = []
        # -- Get Header -- #
        thead = table.find_element(By.TAG_NAME, "thead")
        olv_c_table__thead_ths = thead.find_elements(By.TAG_NAME, "th")
        for index, th in enumerate(olv_c_table__thead_ths):
            if th.get_attribute("data-key"):
                columns.append(th.get_attribute("data-key"))
                index_columns.append(index)
        # -- Get Data -- #
        tbodys = table.find_elements(By.TAG_NAME, "tbody")
        for tbody in tbodys:
            olv_c_table__tds = tbody.find_elements(By.TAG_NAME, "td")
            olv_c_table__tds = [olv_c_table__tds[i] for i in index_columns]
            row.append([olv_c_table__td.text for olv_c_table__td in olv_c_table__tds])
        # -- Dataframe -- #
        return pd.DataFrame(
            columns=columns,
            data=row,
        )

    @retry_if_exception()
    def read_mail(self, mail_id: int | str) -> str:
        self.logger.info(f"Đọc Mail {mail_id}")
        inputSearch = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    'input[placeholder="このメールボックスのメール・電話を検索"]',
                )
            )
        )
        inputSearch.clear()
        time.sleep(self.retry_interval)
        inputSearch.send_keys(mail_id)
        time.sleep(self.retry_interval)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[title="検索"]'))).click()
        time.sleep(self.retry_interval)
        while self.browser.find_elements(By.CSS_SELECTOR, "div[class='loader']"):
            time.sleep(self.retry_interval)
            continue
        iframe = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[id='ifmMain']")))
        self.browser.switch_to.frame(iframe)
        olv_p_mail_view_body__text = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "pre[class='olv-p-mail-view-body__text']"))
        )
        if olv_p_mail_view_body__text.get_attribute("style") != "display: none;":
            return olv_p_mail_view_body__text.text
        else:
            self.wait.until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[id='html-mail-body-if']"))
            )
            body = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            return body.text

    @retry_if_exception()
    def get_status(self, mail_id: int | str) -> str:
        self.logger.info(f"Đọc Mail {mail_id}")
        inputSearch = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    'input[placeholder="このメールボックスのメール・電話を検索"]',
                )
            )
        )
        inputSearch.clear()
        time.sleep(self.retry_interval)
        inputSearch.send_keys(mail_id)
        time.sleep(self.retry_interval)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[title="検索"]'))).click()
        time.sleep(self.retry_interval)
        while self.browser.find_elements(By.CSS_SELECTOR, "div[class='loader']"):
            time.sleep(self.retry_interval)
            continue
        pass

    @retry_if_exception(
        exceptions=(
            StaleElementReferenceException,
            ElementClickInterceptedException,
            ElementNotFoundError,
            ElementNotInteractableException,
        ),
        failure_return=(False, None),
    )
    def reply(
        self,
        mail_id: int | str | None = None,
        reply_to: str | None = None,
        quote: str | None = None,
        to_from: str | None = None,
        signature: str | None = None,
        templates: list[str] | None = None,
        attachments: list[str] = [],  # noqa
    ) -> tuple[bool, str]:
        self.logger.info(f"Trả lời mail: {mail_id}")
        for win in self.browser.window_handles:
            if win != self.root_window:
                self.browser.switch_to.window(win)
                self.browser.close()
                time.sleep(self.retry_interval)
                self.browser.switch_to.window(self.root_window)
        self.browser.switch_to.window(self.root_window)
        inputSearch = self.wait.until(
            EC.element_to_be_clickable(
                (
                    By.CSS_SELECTOR,
                    'input[placeholder="このメールボックスのメール・電話を検索"]',
                )
            )
        )
        inputSearch.clear()
        time.sleep(self.retry_interval)
        inputSearch.send_keys(mail_id)
        time.sleep(self.retry_interval)
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[title="検索"]'))).click()
        time.sleep(self.retry_interval)
        while self.browser.find_elements(By.CSS_SELECTOR, "div[class='loader']"):
            time.sleep(self.retry_interval)
            continue
        time.sleep(self.retry_interval)
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, "iframe[id='ifmMain']")))
        try:
            snackbar__wrap = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class='snackbar__wrap']"))
            )
            if snackbar__wrap.text in [
                "このメールには既に返信されています。",
                "このメールに関する 一時保存メール が存在します。そちらから編集してください。",
            ]:
                self.logger.info(f"Mail {mail_id}: {snackbar__wrap.text}")
                return True, snackbar__wrap.text
        except TimeoutException:
            pass
        while not self.browser.find_elements(By.CSS_SELECTOR, "div[class='menu__content']"):
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[class="menu"]'))).click()
            time.sleep(self.retry_interval)
        menu_content = self.browser.find_element(By.CSS_SELECTOR, "div[class='menu__content']")
        if reply_to:
            option = menu_content.find_element(By.XPATH, f".//label[.//div[text()='{reply_to}']]")
            self.wait.until(EC.element_to_be_clickable(option)).click()
        if quote:
            option = menu_content.find_element(By.XPATH, f".//label[.//div[text()='{quote}']]")
            self.wait.until(EC.element_to_be_clickable(option)).click()
        if to_from:
            label = menu_content.find_element(By.XPATH, ".//label[text()='To / From']")
            div = label.find_element(By.XPATH, "following-sibling::div[1]")
            self.wait.until(EC.element_to_be_clickable(div)).click()
            while not div.find_elements(By.CSS_SELECTOR, "div[class='list__wrap']"):
                time.sleep(self.retry_interval)
                self.wait.until(EC.element_to_be_clickable(div)).click()
                time.sleep(self.retry_interval)
            list_wrap = div.find_element(By.CSS_SELECTOR, "div[class='list__wrap']")
            option = list_wrap.find_element(By.XPATH, f".//li[text()='{to_from}']")
            self.wait.until(EC.element_to_be_clickable(option)).click()
            time.sleep(self.retry_interval)
        if signature:
            label = menu_content.find_element(By.XPATH, ".//label[text()='署名']")
            while True:
                div = label.find_element(By.XPATH, "following-sibling::div[1]")
                if div.find_elements(By.CSS_SELECTOR, "div[class='list__wrap']"):
                    break
                div = label.find_element(By.XPATH, "following-sibling::div[1]")
                self.wait.until(EC.element_to_be_clickable(div)).click()
                time.sleep(self.retry_interval)
            signature = menu_content.find_element(By.XPATH, f".//li[text()='{signature}']")
            self.wait.until(EC.element_to_be_clickable(signature)).click()
        if templates:
            label = menu_content.find_element(By.XPATH, ".//label[text()='テンプレート']")
            div = label.find_element(By.XPATH, "following-sibling::div[1]")
            dropdown_divs = div.find_elements(By.CSS_SELECTOR, "div[class^='dropdown ']")
            for index, value in enumerate(templates):
                if value is None:
                    continue
                self.wait.until(EC.element_to_be_clickable(dropdown_divs[index])).click()
                while not dropdown_divs[index].find_elements(By.CSS_SELECTOR, "div[class='list__wrap']"):
                    time.sleep(self.retry_interval)
                    self.wait.until(EC.element_to_be_clickable(dropdown_divs[index]))
                    dropdown_divs[index].click()
                    time.sleep(self.retry_interval)
                list_wrap_div = dropdown_divs[index].find_element(By.CSS_SELECTOR, "div[class='list__wrap']")
                option = list_wrap_div.find_element(By.XPATH, f".//li[text()='{value}']")
                self.wait.until(EC.element_to_be_clickable(option)).click()
                time.sleep(self.retry_interval)
        self.wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[text()='メール作成']"))).click()
        # -- Switch to new window -- #
        time.sleep(self.retry_interval)
        while not len(self.browser.window_handles) > 1:
            continue
        for window in self.browser.window_handles:
            if window != self.root_window:
                self.browser.switch_to.window(window)
                self.browser.maximize_window()
                break
        # ----- Wait ----- #
        time.sleep(2)
        while self.browser.execute_script("return document.readyState") != "complete":
            time.sleep(self.retry_interval)
        time.sleep(2)
        # ----- Attachments ----- #
        for attachment in attachments:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][multiple]"))
            ).send_keys(attachment)
            # Wait
            time.sleep(2.5)
            self.browser.find_element(By.XPATH, f"//a[contains(text(), '{os.path.basename(attachment)}')]")
            time.sleep(0.5)
            self.logger.info(f"Đính kèm file: {attachment} thành công")
        # ----- Edit (Abstract) ----- #
        ToEmail = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='fTo[]']")))
        ToEmail = ToEmail.get_attribute("value")
        if match := re.search(r"<([^<>]+)>", ToEmail):
            ToEmail = match.group(1)
        bodyMail = None
        try:
            textarea = self.wait.until(method=EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[id='fBody']")))
            old_content = textarea.get_attribute("value")
            if old_content == "":
                raise TimeoutException()
            last_name = self.email_to_lastname.get(ToEmail.lower(), "ご担当者")
            if last_name != "ご担当者":
                bodyMail = old_content.replace("○○", last_name)
            else:
                bodyMail = old_content.replace("○○様", last_name)
            textarea.clear()
            time.sleep(self.retry_interval)
            textarea.send_keys(bodyMail)
            time.sleep(self.retry_interval)
        except TimeoutException:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
            body = self.browser.find_element(By.TAG_NAME, "body")
            divs = body.find_elements(By.TAG_NAME, "div")
            for div in divs:
                if "○○" in div.get_attribute("innerHTML"):
                    last_name = self.email_to_lastname.get(ToEmail.lower(), "ご担当者")
                    if last_name != "ご担当者":
                        bodyMail = div.get_attribute("innerHTML").replace("○○", last_name)
                    else:
                        bodyMail = div.get_attribute("innerHTML").replace("○○様", last_name)
                    self.browser.execute_script("arguments[0].innerHTML = arguments[1];", div, bodyMail)
                    break
            self.browser.switch_to.default_content()
        # ----- Send ----- #
        while not self.browser.find_elements(By.CSS_SELECTOR, "div[class='menu__content']"):
            self.wait.until(EC.element_to_be_clickable(((By.CSS_SELECTOR, "div[class='menu']")))).click()
            time.sleep(self.retry_interval)
        menu_content = self.browser.find_element(By.CSS_SELECTOR, "div[class='menu__content']")
        SaveTempBTN = menu_content.find_element(By.XPATH, ".//button[text()='送信確認']")
        self.wait.until(EC.element_to_be_clickable(SaveTempBTN)).click()
        time.sleep(0.5)
        self.wait.until(EC.presence_of_element_located((By.XPATH, ".//button[text()='送信 ']"))).click()
        time.sleep(self.retry_interval)
        while self.browser.execute_script("return document.readyState") != "complete":
            time.sleep(self.retry_interval)
        time.sleep(self.retry_interval)
        self.browser.switch_to.window(self.root_window)
        time.sleep(self.retry_interval)
        self.logger.info(f"Trả lời mail: {mail_id} thành công")
        return True, bodyMail
