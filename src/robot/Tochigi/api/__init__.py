import logging
import os
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests


class APISharePoint:
    def __init__(
        self,
        TENANT_ID: str,
        CLIENT_ID: str,
        CLIENT_SECRET: str,
    ):
        self.TENANT_ID = TENANT_ID
        self.CLIENT_ID = CLIENT_ID
        self.CLIENT_SECRET = CLIENT_SECRET
        self.logger = logging.getLogger("APISharePoint")

    @classmethod
    def get_site_from_url(cls, url: str) -> str:
        import re
        from urllib.parse import unquote, urlparse

        url = unquote(url)
        parsed = urlparse(url)
        path = parsed.path
        # Case 1: /sites/<site_name>/
        match1 = re.search(r"/sites/([^/]+)/", path)
        if match1:
            return match1.group(1)
        # Case 2: /:f:/s/<site_name>/
        match2 = re.search(r"/:[a-z]:/s/([^/]+)/", path)
        if match2:
            return match2.group(1)
        return None

    def _get_access_token(self):
        response = requests.post(
            url=f"https://login.microsoftonline.com/{self.TENANT_ID}/oauth2/v2.0/token",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        return response.json().get("access_token")

    def get_site(self, site_name: str) -> dict:
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/nskkogyo.sharepoint.com:/sites/{site_name}",
            headers={"Authorization": self._get_access_token()},
        )
        return response.json()

    def get_drives(self, site_name: str) -> dict:
        token = self._get_access_token()
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/nskkogyo.sharepoint.com:/sites/{site_name}",
            headers={"Authorization": token},
        )
        site_id = response.json().get("id")
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives", headers={"Authorization": token}
        )
        return response.json().get("value")

    def get_items_from_drive(self, drive_id: str) -> dict:
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root/children",
            headers={"Authorization": self._get_access_token()},
        )
        return response.json()

    def get_item_from_another_item(self, site_id: str, drive_id: str, item_id: str) -> dict:
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{item_id}/children",
            headers={"Authorization": f"Bearer {self._get_access_token()}"},
        )
        return response.json()

    def get_metadata(self, site_id: str, breadcrumb: str) -> dict:
        """
        Lấy metadata của 1 file hoặc folder trên SharePoint dựa trên site_id và breadcrumb.

        :param site_id: ID của site SharePoint
        :param breadcrumb: Đường dẫn thư mục/file (folder1/folder2/file.txt)
        :return: Metadata của item (file/folder)
        """
        token = self._get_access_token()
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
        drive_id = None
        # Lấy drive_id của site
        while True:
            drive_resp = requests.get(url=url, headers={"Authorization": f"Bearer {token}"})
            drive_resp.raise_for_status()
            drives = drive_resp.json().get("value")
            for drive in drives:
                if drive.get("name") == breadcrumb.split("/")[0]:
                    drive_id = drive.get("id")
                    break
            if drive_id:
                break
            if drive_resp.json().get("@odata.nextLink", None):
                url = drive_resp.json().get("@odata.nextLink")
            else:
                break
        # Truy vấn item dựa trên breadcrumb
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{"/".join(breadcrumb.split("/")[1:])}"
        resp = requests.get(url, headers={"Authorization": token})
        return resp.json()

    def read_excel(
        self,
        drive_id: str,
        item_id: str,
    ) -> Any:
        sheets = {}
        token = self._get_access_token()
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/workbook/worksheets",
            headers={"Authorization": token},
        )
        for sheet in response.json().get("value"):
            name = sheet.get("name")
            response = requests.get(
                url=f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/workbook/worksheets/{name}/usedRange",
                headers={"Authorization": token},
            )
            sheets[name] = response.json().get("values", [])
        return sheets

    def download_item(self, site_id: str, breadcrumb: str, save_to: str) -> bool:
        try:
            self.logger.info(f"Download {site_id}:/{breadcrumb}")
            headers = {"Authorization": self._get_access_token()}
            # B1: Resolve breadcrumb để lấy metadata
            item_metadata = requests.get(
                url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{breadcrumb}",
                headers=headers,
            ).json()
            drive_id = item_metadata["parentReference"]["driveId"]
            item_id = item_metadata["id"]
            name = item_metadata["name"]

            if "folder" in item_metadata:
                # Là folder
                folder_path = os.path.join(save_to, name)
                os.makedirs(folder_path, exist_ok=True)

                # Lấy danh sách các item trong folder
                children = (
                    requests.get(
                        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/children", headers=headers
                    )
                    .json()
                    .get("value", [])
                )

                # Tải từng item trong thư mục
                for child in children:
                    child_name = child["name"]
                    child_path = f"{breadcrumb}/{child_name}"
                    self.download_item(site_id, child_path, folder_path)
            else:
                # Là file
                file_path = os.path.join(save_to, name) if os.path.isdir(save_to) else save_to

                response = requests.get(
                    url=f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content",
                    headers=headers,
                    stream=True,
                )

                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            self.logger.info(f"Save to: {save_to}")
            return True
        except Exception:
            return False

    def download_drive(
        self,
        drive_id: str,
        breadcrumb: str,
        save_to: str,
    ):
        self.logger.info(f"Download drive: {drive_id}:/{breadcrumb}")
        result = []

        def download_file(url, save_path):
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            r = requests.get(url)
            r.raise_for_status()
            with open(save_path, "wb") as f:
                f.write(r.content)
            self.logger.info(save_path)

        encoded_path = quote(breadcrumb)
        api_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{encoded_path}:/children"

        res = requests.get(api_url, headers={"Authorization": f"Bearer {self._get_access_token()}"})
        # res.raise_for_status()
        items = res.json().get("value", [])

        for item in items:
            if "file" in item:  # Nếu là file
                download_url = item["@microsoft.graph.downloadUrl"]
                file_name = item["name"]
                save_path = os.path.join(save_to, file_name)
                download_file(download_url, save_path)
                result.append((download_url, os.path.abspath(save_path), ""))

            elif "folder" in item:  # Nếu là folder → duyệt đệ quy
                folder_name = item["name"]
                new_path = f"{breadcrumb}/{folder_name}"
                new_local_dir = os.path.join(save_to, folder_name)
                return self.download_drive(drive_id, new_path, new_local_dir)

        return result

    def upload_item(
        self,
        site_id: str,
        local_path: str,
        breadcrumb: str = "",
        replace: bool = False,
    ) -> dict:
        """
        Upload file từ local lên SharePoint site theo breadcrumb.

        :param site_id: ID của site SharePoint (vd: từ get_site(...))
        :param local_path: File local (tên file sẽ giữ nguyên)
        :param breadcrumb: Thư mục trên SharePoint (folder1/folder2)
        :param replace: Nếu True thì ghi đè, False thì bỏ qua nếu đã tồn tại
        :return: Metadata file đã upload hoặc tồn tại
        """
        token = self._get_access_token()
        file_name = os.path.basename(local_path)
        # Lấy default drive của site
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive", headers={"Authorization": token}
        )
        drive_id = response.json().get("id")

        # Ghép full path
        if breadcrumb:
            full_path = f"{breadcrumb.strip('/')}/{file_name}"
        else:
            full_path = file_name

        # Kiểm tra file tồn tại
        check_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{full_path}"
        check_response = requests.get(check_url, headers={"Authorization": token})
        if check_response.status_code == 200 and not replace:
            return check_response.json()
        with open(local_path, "rb") as f:
            content = f.read()
        upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{full_path}:/content"
        upload_response = requests.put(
            upload_url,
            headers={"Authorization": token, "Content-Type": "application/octet-stream"},
            data=content,
        )
        if "error" in upload_response.json():
            self.logger.error(upload_response.json())
        else:
            self.logger.info(f"Upload {local_path} to {site_id}:{breadcrumb}")
        return upload_response.json()

    def rename_breadcrumd(self, site_id: str, drive_id: str, item_id: str, new_name: str) -> bool:
        response = requests.patch(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{item_id}",
            headers={"Authorization": f"Bearer {self._get_access_token()}", "Content-Type": "application/json"},
            json={
                "name": new_name,
            },
        )
        if response.status_code == 200:
            self.logger.info(response.json())
        else:
            self.logger.error(response.json())
        return response.status_code == 200

    def write(
        self,
        site_id: str,
        drive_id: str,
        item_id: str,
        range: str,
        data: list,
        sheet: str = "Sheet1",
    ) -> bool:
        data = {"values": data}
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/items/{item_id}/workbook/worksheets('{sheet}')/range(address='{range}')"
        response = requests.patch(
            url=url,
            json=data,
            headers={"Authorization": f"Bearer {self._get_access_token()}", "Content-Type": "application/json"},
        )
        if "error" in response.json():
            self.logger.error(response.json())
        else:
            self.logger.info(response.json())
        return response.status_code == 200

    def get_lists(
        self,
        site_id: str,
    ):
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
        response = requests.get(
            url=url,
            headers={"Authorization": f"Bearer {self._get_access_token()}"},
        )
        if response.status_code != 200:
            return response.json()
        response = response.json()
        return response.get("value")

    def get_list(self, site_id: str, list_id: str) -> pd.DataFrame:
        data = []
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?expand=fields"
        while True:
            response = requests.get(
                url=url,
                headers={
                    "Authorization": f"Bearer {self._get_access_token()}",
                },
            ).json()
            value = response.get("value", [])
            if value:
                data.extend([v.get("fields", {}) for v in value])
            if "@odata.nextLink" not in response:
                break
            url = response["@odata.nextLink"]
        return pd.DataFrame(data)

    def add_to_list(
        self,
        site_id: str,
        list_id: str,
        fields: dict,
    ) -> bool:
        self.logger.info(f"Insert {fields.values()}")
        response = requests.post(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items",
            headers={
                "Authorization": f"Bearer {self._get_access_token()}",
            },
            json={"fields": fields},
        )
        return response.status_code == 201
