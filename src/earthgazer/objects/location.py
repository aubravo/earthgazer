from __future__ import annotations

from typing import TypeVar

from sqlmodel import Field, Session, SQLModel, select

T = TypeVar("T", bound="Location")

class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(description="The name of the location")
    latitude: float = Field(description="The latitude of the location")
    longitude: float = Field(description="The longitude of the location")

    @classmethod
    def create(cls: type[T], session: Session, name: str, latitude: float, longitude: float) -> T:
        location = cls(name=name, latitude=latitude, longitude=longitude)
        session.add(location)
        session.commit()
        session.refresh(location)  # This updates the object with the generated id
        return location

    @classmethod
    def get_by_name(cls: type[T], session: Session, name: str) -> T:
        statement = select(cls).where(cls.name == name)
        result = session.exec(statement).first()
        return result

    @classmethod
    def update_location(cls: type[T], session: Session, location_id: int,
                        latitude: float | None = None, longitude: float | None = None) -> T:
        location = session.get(cls, location_id)
        if location:
            if latitude is not None:
                location.latitude = latitude
            if longitude is not None:
                location.longitude = longitude
            session.commit()
            session.refresh(location)
        return location

    @classmethod
    def delete_location(cls: type[T], session: Session, location_id: int) -> T:
        location = session.get(cls, location_id)
        if location:
            session.delete(location)
            session.commit()
        return location
