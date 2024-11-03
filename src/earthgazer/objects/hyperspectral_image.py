from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from typing import TypeVar

from sqlmodel import Field, Session, SQLModel, select

T = TypeVar("T", bound="HyperspectralImage")

class HyperspectralImage(SQLModel, table=True):
    image_id: int | None = Field(default=None, primary_key=True)
    source_image_id: str = Field(description="The ID of the source image")
    source_path: str = Field(description="The source storage location of the hyperspectral image")
    storage_location: str = Field(description="The storage location of the hyperspectral image")
    sensing_timestamp: datetime = Field(description="The time when the image was sensed")
    mission_id: str = Field(description="The ID of the mission")
    north_latitude: float = Field(description="The northern latitude of the image coverage")
    south_latitude: float = Field(description="The southern latitude of the image coverage")
    west_longitude: float = Field(description="The western longitude of the image coverage")
    east_longitude: float = Field(description="The eastern longitude of the image coverage")
    atmospheric_reference_level: float = Field(description="The atmospheric reference level")
    acquisition_timestamp: datetime = Field(description="The date and time when the image was acquired")

    @classmethod
    def create(cls: type[T],
                session: Session,
                source_image_id: str,
                source_path: str,
                storage_location: str,
                sensing_timestamp: datetime,
                mission_id: str,
                north_latitude: float,
                south_latitude: float,
                west_longitude: float,
                east_longitude: float,
                atmospheric_reference_level: float,
                acquisition_timestamp: datetime,
                ) -> T:
        image = cls(
            source_image_id=source_image_id,
            source_path=source_path,
            storage_location=storage_location,
            sensing_timestamp=sensing_timestamp,
            mission_id=mission_id,
            north_latitude=north_latitude,
            south_latitude=south_latitude,
            west_longitude=west_longitude,
            east_longitude=east_longitude,
            atmospheric_reference_level=atmospheric_reference_level,
            acquisition_timestamp=acquisition_timestamp,
            )
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    @classmethod
    def get_by_image_id(cls: type[T], session: Session, image_id: int) -> T:
        statement = select(cls).where(cls.image_id == image_id)
        result = session.exec(statement).first()
        return result

    @classmethod
    def get_by_source_image_id(cls: type[T], session: Session, source_image_id: str) -> T:
        statement = select(cls).where(cls.source_image_id == source_image_id)
        result = session.exec(statement).first()
        return result

    @classmethod
    def update_image(cls: type[T], session: Session, image_id: int,
                     storage_location: str | None = None,
                     sensing_timestamp: datetime | None = None,
                     north_latitude: float | None = None,
                     south_latitude: float | None = None,
                     west_longitude: float | None = None,
                     east_longitude: float | None = None,
                     atmospheric_reference_level: float | None = None) -> T:
        image = session.get(cls, image_id)
        if image:
            if storage_location is not None:
                image.storage_location = storage_location
            if sensing_timestamp is not None:
                image.sensing_time = sensing_timestamp
            if north_latitude is not None:
                image.north_latitude = north_latitude
            if south_latitude is not None:
                image.south_latitude = south_latitude
            if west_longitude is not None:
                image.west_longitude = west_longitude
            if east_longitude is not None:
                image.east_longitude = east_longitude
            if atmospheric_reference_level is not None:
                image.atmospheric_reference_level = atmospheric_reference_level
            session.commit()
            session.refresh(image)
        return image

    @classmethod
    def delete_image(cls: type[T], session: Session, image_id: int) -> T:
        image = session.get(cls, image_id)
        if image:
            session.delete(image)
            session.commit()
        return image
