from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import Engine
from sqlmodel import create_engine


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    # App
    DEBUG: bool = False
    ROOT_PATH: str = "/api"
    APP_NAME: str = "Orchestration Server"
    # DATABASE
    MYSQL_SERVER: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USERNAME: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str = "RobotNSK"
    # REDIS
    REDIS_PASSWORD: str = ""
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    # MINIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "robot"
    # WEB ACCESS
    WEBACCESS_USERNAME: str
    WEBACCESS_PASSWORD: str
    # SHAREPOINT
    SHAREPOINT_DOMAIN: str
    SHAREPOINT_EMAIL: str
    SHAREPOINT_PASSWORD: str
    # POWER APP
    POWER_APP_USERNAME: str
    POWER_APP_PASSWORD: str
    # MAIL DEALER
    MAIL_DEALER_USERNAME: str
    MAIL_DEALER_PASSWORD: str
    # API SHAREPOINT
    API_SHAREPOINT_TENANT_ID: str
    API_SHAREPOINT_CLIENT_ID: str
    API_SHAREPOINT_CLIENT_SECRET: str

    @computed_field
    @property
    def MYSQL_CONNECTION_STRING(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USERNAME}:{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    @computed_field
    @property
    def REDIS_CONNECTION_STRING(self) -> str:
        return f"redis://{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @computed_field
    @property
    def db_engine(self) -> Engine:
        return create_engine(self.MYSQL_CONNECTION_STRING)


settings = Settings()
