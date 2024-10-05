from __future__ import annotations

from typing import TypeVar
from datetime import datetime

from sqlmodel import Field, Session, SQLModel, select

T = TypeVar("T", bound="HyperspectralImage")

class HyperspectralImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(description="The source of the hyperspectral image")
    storage_location: str = Field(description="The storage location of the hyperspectral image")
    acquisition_date: datetime = Field(description="The date and time when the image was acquired")
    spectral_range_start: float = Field(description="The start of the spectral range in nanometers")
    spectral_range_end: float = Field(description="The end of the spectral range in nanometers")
    spatial_resolution: float = Field(description="The spatial resolution in meters")

    @classmethod
    def create(cls: type[T], session: Session, source: str, storage_location: str, 
               acquisition_date: datetime, spectral_range_start: float, 
               spectral_range_end: float, spatial_resolution: float) -> T:
        image = cls(source=source, storage_location=storage_location,
                    acquisition_date=acquisition_date, spectral_range_start=spectral_range_start,
                    spectral_range_end=spectral_range_end, spatial_resolution=spatial_resolution)
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
                     spectral_range_start: float | None = None,
                     spectral_range_end: float | None = None,
                     spatial_resolution: float | None = None) -> T:
        image = session.get(cls, image_id)
        if image:
            if storage_location is not None:
                image.storage_location = storage_location
            if spectral_range_start is not None:
                image.spectral_range_start = spectral_range_start
            if spectral_range_end is not None:
                image.spectral_range_end = spectral_range_end
            if spatial_resolution is not None:
                image.spatial_resolution = spatial_resolution
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
