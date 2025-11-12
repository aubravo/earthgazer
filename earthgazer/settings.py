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


class EarthGazerSettings(BaseSettings):
    database: DatabaseManagerSettings = DatabaseManagerSettings()
    gcloud: GcloudSettings = GcloudSettings()
    model_config = SettingsConfigDict(env_file=".env", env_nested_delimiter="__", env_prefix="earthgazer__")
