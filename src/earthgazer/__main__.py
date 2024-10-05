import earthgazer.__about__ as about
from earthgazer.env_management.logger import setup_logger
from earthgazer.env_management.settings import Settings
from earthgazer.objects.hyperspectral_image import HyperspectralImage
from sqlmodel import Session, create_engine
from datetime import datetime

# Set up the logger
logger = setup_logger(__name__)

settings = Settings()

# Create a SQLite database engine (you might want to move this to a separate database configuration file)
engine = create_engine("sqlite:///earthgazer.db")

def main() -> None:
    logger.info(about.__logo__)
    logger.info(f"earthgazer version {about.__version__}")
    logger.info(f"Test setting: {settings.test_setting}")

    # Example usage of HyperspectralImage
    with Session(engine) as session:
        # Create a new hyperspectral image
        new_image = HyperspectralImage.create(
            session=session,
            source="Satellite X",
            storage_location="/path/to/image.tif",
            acquisition_date=datetime.now(),
            spectral_range_start=400.0,
            spectral_range_end=2500.0,
            spatial_resolution=30.0
        )
        logger.info(f"Created new hyperspectral image with ID: {new_image.id}")

        # Retrieve the image
        retrieved_image = HyperspectralImage.get_by_source(session, "Satellite X")
        logger.info(f"Retrieved image: {retrieved_image.source}, {retrieved_image.acquisition_date}")

        # Update the image
        updated_image = HyperspectralImage.update_image(
            session=session,
            image_id=new_image.id,
            storage_location="/new/path/to/image.tif"
        )
        logger.info(f"Updated image storage location: {updated_image.storage_location}")

        # Delete the image
        deleted_image = HyperspectralImage.delete_image(session, new_image.id)
        logger.info(f"Deleted image with ID: {deleted_image.id}")

    logger.info("EarthGazer application finished")

if __name__ == "__main__":
    main()
