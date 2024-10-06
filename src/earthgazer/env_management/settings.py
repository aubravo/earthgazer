from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Define the settings here
    test_setting: str = Field(default="default value")

    # Settings configuration
    model_config = SettingsConfigDict(
        env_prefix="EARTHGAZER_",
        extra="ignore",
    )
