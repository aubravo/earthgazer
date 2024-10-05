from earthgazer.logger import setup_logger

# Set up the logger
logger = setup_logger(__name__)

def main():
    logger.info("Starting EarthGazer application")
    logger.debug("This is a debug message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.info("EarthGazer application finished")

if __name__ == "__main__":
    main()
