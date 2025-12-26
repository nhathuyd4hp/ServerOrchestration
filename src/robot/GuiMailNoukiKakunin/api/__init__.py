import logging
import os

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

    def download_item(self, site_id: str, breadcrumb: str, save_to: str) -> str | None:
        headers = {"Authorization": self._get_access_token()}
        item_metadata = requests.get(
            url=f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root:/{breadcrumb}",
            headers=headers,
        ).json()
        drive_id = item_metadata["parentReference"]["driveId"]
        item_id = item_metadata["id"]
        name = item_metadata["name"]
        response = requests.get(
            url=f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{item_id}/content",
            headers=headers,
            stream=True,
        )
        if response.status_code != 200:
            return None
        os.makedirs(save_to, exist_ok=True)
        save_path = os.path.join(save_to, name)
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return os.path.abspath(save_path)
