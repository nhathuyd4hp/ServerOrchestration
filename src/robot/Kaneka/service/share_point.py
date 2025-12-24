import re
import time
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.robot.Kaneka.common.decorator import retry_if_exception
from src.robot.Kaneka.core import IWebDriver


class SharePoint(IWebDriver):
    def __init__(self, url: str, username: str, password: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url
        self.authenticated = self._authentication(username, password)
        if not self.authenticated:
            raise Exception("Kiểm tra thông tin xác thực")

    @retry_if_exception(
        exceptions=(
            TimeoutException,
            ElementClickInterceptedException,
            StaleElementReferenceException,
        ),
        max_retries=3,
        failure_return=False,
    )
    def _authentication(self, username: str, password: str) -> bool:
        self._navigate("https://login.microsoftonline.com/")
        if self.browser.current_url.startswith("https://m365.cloud.microsoft"):
            self.logger.info("Xác thực thành công!")
            return True
        # -- Username
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="email"]'))).send_keys(
                username
            )
            # -- Next
            btn = self.wait.until(EC.presence_of_element_located((By.ID, "idSIButton9")))
            self.wait.until(EC.element_to_be_clickable(btn)).click()
            # -- Password
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="password"]'))).send_keys(password)
            # -- Sign in
            self.wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
        except TimeoutException:
            alert = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='alert']")))
            self.logger.error(alert.text)
            return False

        try:  # Password Error
            alert = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='alert']")))
            self.logger.error(alert.text)
            return False
        except TimeoutException:
            pass
        # -- Stay Signed In
        self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[id='idSIButton9']"))).click()
        time.sleep(1)
        self._navigate(self.url)
        if self.browser.current_url.find(".sharepoint.com") == -1:
            self.logger.info(" Xác thực thất bại!")
            return False
        self.logger.info("Xác thực thành công!")
        return True

    @retry_if_exception(
        exceptions=(
            StaleElementReferenceException,
            ElementClickInterceptedException,
            TimeoutException,
        ),
        failure_return=(None, pd.DataFrame()),
    )
    def search(self, site_url: str, keyword: int | str | None = None) -> Tuple[str, pd.DataFrame]:
        self._navigate(site_url)
        for w in self.browser.window_handles:
            if w != self.root_window:
                self.browser.switch_to.window(w)
                self.browser.close()
        self.browser.switch_to.window(self.root_window)
        if keyword:
            inputSearch = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='search']")))
            inputSearch.clear()
            time.sleep(self.retry_interval)
            inputSearch.send_keys(keyword)
            time.sleep(self.retry_interval)
            self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[title='Search']"))).click()
            time.sleep(self.retry_interval)
            WebDriverWait(
                driver=self.browser,
                timeout=60,
                poll_frequency=self.retry_interval,
            ).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[@title='Clear filter' and contains(normalize-space(.), '{keyword}')]")
                )
            )
            #
            time.sleep(10)
            header = self.wait.until(
                method=EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-automationid='DetailsHeader']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-automationid='row-header']")),
                ),
                message="Không tìm thấy tiêu đề",
            )
            columns = header.find_elements(By.CSS_SELECTOR, "div[role='columnheader'],div[tag='columnheader']")
            columns = [
                (
                    column.get_attribute("title")
                    if column.get_attribute("title")
                    else re.sub(r"[\ue000-\uf8ff]|\n|Press C to open file hover card", "", column.text)
                )
                for column in columns
            ]
            rows = self.wait.until(
                method=EC.any_of(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div[role='presentation'][data-automationid='ListCell']")
                    ),
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[id^='virtualized-list'][role='row']")),
                ),
                message="Không tìm thấy dữ liệu",
            )
            for row in rows:
                cells = row.find_elements(
                    By.CSS_SELECTOR, "div[role='gridcell'], div[data-automationid='field-InternalAddColumn']"
                )
                if [cell.text for cell in cells][columns.index("Type")] == "":
                    Folder = cells[columns.index("Name")].text
                    ActionChains(self.browser).double_click(cells[columns.index("Name")]).perform()
                    self.wait.until(
                        EC.presence_of_element_located(
                            (
                                By.XPATH,
                                f"//div[@type='button' and @data-automationid='breadcrumb-crumb' and normalize-space(.)='{Folder}']",  # noqa
                            )
                        )
                    )
                    break
            self.wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[@title='Clear filter' and contains(normalize-space(.), '{keyword}')]")
                )
            ).click()
            time.sleep(2.5)
            self.wait.until(
                EC.invisibility_of_element_located(
                    (By.XPATH, f"//button[@title='Clear filter' and contains(normalize-space(.), '{keyword}')]")
                )
            )
        # Header
        header = self.wait.until(
            method=EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-automationid='DetailsHeader']")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-automationid='row-header']")),
            ),
            message="Không tìm thấy tiêu đề",
        )
        columns = header.find_elements(By.CSS_SELECTOR, "div[role='columnheader'],div[tag='columnheader']")
        columns = [
            (
                column.get_attribute("title")
                if column.get_attribute("title")
                else re.sub(r"[\ue000-\uf8ff]|\n|Press C to open file hover card", "", column.text)
            )
            for column in columns
        ]
        # Rows
        data = []
        rows = self.wait.until(
            method=EC.any_of(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[role='presentation'][data-automationid='ListCell']")
                ),
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[id^='virtualized-list'][role='row']")),
            ),
            message="Không tìm thấy dữ liệu",
        )
        for row in rows:
            cells = row.find_elements(
                By.CSS_SELECTOR, "div[role='gridcell'], div[data-automationid='field-InternalAddColumn']"
            )
            append_row = []
            for cell in cells:
                if imgs := cell.find_elements(By.TAG_NAME, "img"):
                    img = imgs[0]
                    file_type = img.get_attribute("alt")
                    file_type = file_type.replace(".", "")
                    append_row.append(file_type)
                else:
                    append_row.append(re.sub(r"[\ue000-\uf8ff]|\n|Press C to open file hover card", "", cell.text))
            data.append(append_row)
        data = pd.DataFrame(data=data, columns=columns)
        data.drop(columns="", inplace=True, errors="ignore")
        data.drop(columns="Add column", inplace=True, errors="ignore")
        return self.browser.current_url, data

    @retry_if_exception(
        exceptions=(
            TimeoutException,
            StaleElementReferenceException,
            ElementClickInterceptedException,
        )
    )
    def download(self, site_url: str, file_pattern: str) -> List[Tuple[str, str]]:
        folder = Path(self.download_directory)
        for item in folder.iterdir():
            if item.is_file():
                item.unlink()
        # --- #
        result = []
        self._navigate(site_url)
        self._navigate(site_url)
        self._navigate(site_url)
        WebDriverWait(
            driver=self.browser,
            timeout=60,
            poll_frequency=self.retry_interval,
        ).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class='app-container']")))
        # Folder
        file = file_pattern.split("/")[:-1]
        for step in file:
            time.sleep(self.retry_interval)
            gridcells = self.wait.until(
                EC.any_of(
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div[role='gridcell'][data-automationid='field-LinkFilename']")
                    ),
                    EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, "div[role='gridcell'][data-automation-key^='displayNameColumn']")
                    ),
                )
            )
            for gridcell in gridcells:
                text = re.sub(r"[\ue000-\uf8ff]|\n|Press C to open file hover card", "", gridcell.text)
                if re.match(step, text):
                    button = gridcell.find_element(By.XPATH, './/button | .//span[@role="button"]')
                    self.wait.until(EC.element_to_be_clickable(button)).click()
                    time.sleep(self.retry_interval)
                    self.wait.until(
                        EC.presence_of_element_located(
                            (
                                By.XPATH,
                                f'//div[@type="button" and @data-automationid="breadcrumb-crumb" and text()="{step}"]',
                            )
                        )
                    )
                    break
            time.sleep(self.retry_interval)
        # File
        file = file_pattern.split("/")[-1]
        gridcells = self.wait.until(
            EC.any_of(
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[role='gridcell'][data-automationid='field-LinkFilename']")
                ),
                EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div[role='gridcell'][data-automation-key^='displayNameColumn']")
                ),
            )
        )
        for gridcell in gridcells:
            file_name = re.sub(r"[\ue000-\uf8ff]|\n|Press C to open file hover card", "", gridcell.text)
            if re.match(file, file_name):
                button = gridcell.find_element(By.XPATH, './/button | .//span[@role="button"]')
                self.wait.until(EC.element_to_be_clickable(button))
                time.sleep(self.retry_interval)
                ActionChains(self.browser).context_click(button).perform()
                downloadButton = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "button[data-automationid='downloadCommand']"))
                )
                self.wait.until(EC.element_to_be_clickable(downloadButton)).click()
                time.sleep(5)
                file_path, status = self.wait_for_download_to_finish()
                self.logger.info(f"Tải {file_name}: {file_path if not status else status},")
                result.append((file_path, status))
        return result
