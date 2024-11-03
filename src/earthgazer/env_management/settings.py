from typing import TypeVar

from google.cloud import bigquery
from google.oauth2 import service_account
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

T = TypeVar("T", bound="Settings")

class Settings(BaseSettings):
    # Define the settings here
    TEST_SETTING: str = Field(default="default value")
    BIGQUERY_CREDENTIALS_PATH: str = Field(default="./bigquery-credentials.json")

    # Settings configuration
    model_config = SettingsConfigDict(
        env_prefix="EARTHGAZER_",
        extra="ignore",
    )

    @property
    def google_credentials(self: T) -> service_account.Credentials:
        return service_account.Credentials.from_service_account_file(
            self.BIGQUERY_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

    @property
    def bigquery_client(self: T) -> bigquery.Client:
        return bigquery.Client(credentials=self.google_credentials, project=self.google_credentials.project_id)

# Create a global instance of the Settings
settings = Settings()
