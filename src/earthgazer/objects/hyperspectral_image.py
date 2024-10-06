from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

from typing import TypeVar

from sqlmodel import Field, Session, SQLModel, select
from src.earthgazer.env_management.settings import settings

T = TypeVar("T", bound="HyperspectralImage")

class HyperspectralImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(description="The source of the hyperspectral image")
    storage_location: str = Field(description="The storage location of the hyperspectral image")
    acquisition_date: datetime = Field(description="The date and time when the image was acquired")
    sensing_time: datetime = Field(description="The time when the image was sensed")
    mission_id: str = Field(description="The ID of the mission")
    source_image_id: str = Field(description="The ID of the source image")
    north_latitude: float = Field(description="The northern latitude of the image coverage")
    south_latitude: float = Field(description="The southern latitude of the image coverage")
    west_longitude: float = Field(description="The western longitude of the image coverage")
    east_longitude: float = Field(description="The eastern longitude of the image coverage")
    atmospheric_reference_level: float = Field(description="The atmospheric reference level")

    @classmethod
    def create(cls: type[T], session: Session, source: str, storage_location: str,
               acquisition_date: datetime, sensing_time: datetime, mission_id: str,
               source_image_id: str, north_latitude: float, south_latitude: float,
               west_longitude: float, east_longitude: float, atmospheric_reference_level: float) -> T:
        image = cls(source=source, storage_location=storage_location,
                    acquisition_date=acquisition_date, sensing_time=sensing_time,
                    mission_id=mission_id, source_image_id=source_image_id,
                    north_latitude=north_latitude, south_latitude=south_latitude,
                    west_longitude=west_longitude, east_longitude=east_longitude,
                    atmospheric_reference_level=atmospheric_reference_level)
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    @classmethod
    def get_by_source(cls: type[T], session: Session, source: str) -> T:
        statement = select(cls).where(cls.source == source)
        result = session.exec(statement).first()
        return result

    @classmethod
    def update_image(cls: type[T], session: Session, image_id: int,
                     storage_location: str | None = None,
                     sensing_time: datetime | None = None,
                     north_latitude: float | None = None,
                     south_latitude: float | None = None,
                     west_longitude: float | None = None,
                     east_longitude: float | None = None,
                     atmospheric_reference_level: float | None = None) -> T:
        image = session.get(cls, image_id)
        if image:
            if storage_location is not None:
                image.storage_location = storage_location
            if sensing_time is not None:
                image.sensing_time = sensing_time
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

    @classmethod
    def query_bigquery(cls, query: str) -> list[dict]:
        """
        Execute a BigQuery SQL query and return the results.

        :param query: SQL query string
        :return: List of dictionaries representing the query results
        """
        query_job = settings.bigquery_client.query(query)
        results = query_job.result()
        return [dict(row) for row in results]
