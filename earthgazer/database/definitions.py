from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class Base(DeclarativeBase):
    pass


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": "earthgazer"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    longitude: Mapped[float]
    latitude: Mapped[float]
    from_date: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")
    to_date: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")
