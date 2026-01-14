import base64
import json
import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from sqlalchemy import URL

logging.basicConfig(level=logging.DEBUG)

class DatabaseManagerSettings(BaseSettings, extra="allow"):
    drivername: str = "sqlite"
    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = None
    database: str | None = None
    url: URL | None = None
    echo_sql: bool | None = False

    @model_validator(mode="after")
    def validate_url(self):
        if not self.url:
            _url = URL.create(
                drivername=self.drivername,
                username=self.username,
                password=self.password,
                host=self.host,
                port=self.port,
                database=self.database,
            )
            logging.debug("Derivating URL")
            self.url = _url
        elif isinstance(self.url, str):
            logging.debug("Parsing URL")
            self.url = URL.create(self.url)
        return self


class GcloudSettings(BaseSettings):
    service_account: str | dict | None = None
    bucket_name: str | None = None

    @model_validator(mode="after")
    def validate_service_account(self):

        if not self.service_account:
            logging.debug("Service account is empty, returning None")
            return self

        if isinstance(self.service_account, dict):
            logging.debug("Service account is already a dictionary")
            return self

        logging.debug("Validating service account")

        try:
            self.service_account = base64.b64decode(self.service_account)
        except (ValueError, TypeError):
            logging.debug("Service account is not base64 encoded")

        try:
            self.service_account = json.loads(self.service_account)
            logging.debug("Service account is valid JSON")
        except json.JSONDecodeError:
            raise Exception("Service account is not a valid JSON")

        return self


class CelerySettings(BaseSettings):
    broker_url: str = "redis://redis:6379/0"
    result_backend: str = "redis://redis:6379/1"
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: list[str] = ["json"]
    timezone: str = "UTC"
    enable_utc: bool = True
    worker_concurrency: int = 4
    worker_prefetch_multiplier: int = 2
    task_acks_late: bool = True
    task_reject_on_worker_lost: bool = True
    result_expires: int = 3600  # 1 hour

    @model_validator(mode="after")
    def validate_urls(self):
        logging.debug("Validating Celery broker and result backend URLs")

        if not self.broker_url:
            raise ValueError("Celery broker_url cannot be empty")

        if not self.result_backend:
            raise ValueError("Celery result_backend cannot be empty")

        # Ensure URLs are properly formatted
        if not self.broker_url.startswith(("redis://", "rediss://", "amqp://", "amqps://")):
            raise ValueError(f"Invalid broker_url scheme: {self.broker_url}")

        if not self.result_backend.startswith(("redis://", "rediss://", "db+", "cache+", "rpc://")):
            raise ValueError(f"Invalid result_backend scheme: {self.result_backend}")

        logging.debug(f"Celery broker URL: {self.broker_url}")
        logging.debug(f"Celery result backend: {self.result_backend}")

        return self


class EarthGazerSettings(BaseSettings):
    database: DatabaseManagerSettings = DatabaseManagerSettings()
    gcloud: GcloudSettings = GcloudSettings()
    celery: CelerySettings = CelerySettings()
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", env_prefix="earthgazer__")
