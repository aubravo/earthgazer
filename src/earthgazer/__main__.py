import earthgazer.__about__ as about
from earthgazer.env_management.logger import setup_logger
from earthgazer.env_management.settings import Settings

# Set up the logger
logger = setup_logger(__name__)

settings = Settings()


def main() -> None:
    logger.info(about.__logo__)
    logger.info(f"earthgazer version {about.__version__}")
    logger.info(f"Test setting: {settings.test_setting}")
    logger.info("EarthGazer application finished")


if __name__ == "__main__":
    main()
