import os
from pathlib import Path
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    # BASE DIR
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    # Google Sheet
    APPLICATION_SCRIPTS_URL: str = "https://script.google.com/macros/s/AKfycbwUY_GGn7fsoQCr9Ouq9vz2DIADaEf-hNYtUcwRTM0xNYsJhE_b3HbYFisWnA_CRMDI/exec"
    # Mail Dealer
    MAIL_DEALER_URL: str = "https://mds3310.maildealer.jp/"
    MAIL_DEALER_USERNAME: str = "vietnamrpa"
    MAIL_DEALER_PASSWORD: str = "nsk159753"
    # Share Point
    SHARE_POINT_URL: str = "https://nskkogyo.sharepoint.com/"
    SHARE_POINT_USERNAME: str = "hanh3@nskkogyo.onmicrosoft.com"
    SHARE_POINT_PASSWORD: str = "Got21095"
    # DOWNLOAD DIRECTORY
    @computed_field
    @property
    def DOWNLOAD_DIRECTORY(self) -> str:
        return os.path.join(os.path.abspath(self.BASE_DIR),"downloads")
    # LOG
    LOGGING_LEVEL: str = "INFO"

    @computed_field
    @property
    def LOGGING_FILE(self) -> str:
        return os.path.abspath("bot.log")
    # PROFILE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Duyệt qua các thuộc tính của đối tượng và chuyển Path thành chuỗi
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                self.__dict__[key] = str(value)


setting = Settings()

__all__ = [setting]
