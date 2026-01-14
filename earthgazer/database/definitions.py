import enum

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


class RadiometricMeasure(enum.Enum):
    RADIANCE = "RADIANCE"
    REFLECTANCE = "REFLECTANCE"
    DN = "DN"


class AtmosphericReferenceLevel(enum.Enum):
    TOA = "TOA"
    BOA = "BOA"


class TaskStatus(enum.Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class ProcessingJobStatus(enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"

class Base(DeclarativeBase):
    def add(self, session):
        session.add(self)
        session.commit()


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = {"schema": "earthgazer"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    from_date: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")
    to_date: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    added: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")

class CaptureData(Base):
    __tablename__ = "capture_data"
    __table_args__ = {"schema": "earthgazer"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    main_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    secondary_id: Mapped[str] = mapped_column(String(100))
    mission_id: Mapped[str] = mapped_column(String(100))
    sensing_time: Mapped[DateTime] = mapped_column(DateTime)
    north_lat: Mapped[float]
    south_lat: Mapped[float]
    west_lon: Mapped[float]
    east_lon: Mapped[float]
    base_url: Mapped[str] = mapped_column(String(500))
    cloud_cover: Mapped[float | None] = None
    radiometric_measure: Mapped[str | None] = mapped_column(Enum(RadiometricMeasure), default=None)
    athmospheric_reference_level: Mapped[str | None] = mapped_column(Enum(AtmosphericReferenceLevel), default=None)
    mgrs_tile: Mapped[str | None] = mapped_column(String(100), default=None)
    wrs_path: Mapped[int | None] = mapped_column(Integer, default=None)
    wrs_row: Mapped[int | None] = mapped_column(Integer, default=None)
    data_type: Mapped[str | None] = mapped_column(String(30), default=None)
    backed_up: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_date: Mapped[str | None] = mapped_column(DateTime(timezone=False), default=None)
    backup_location: Mapped[str | None] = mapped_column(String(500), default=None)
    added: Mapped[str] = mapped_column(DateTime(timezone=False), server_default="now()")


class TaskExecution(Base):
    """Track individual Celery task executions for monitoring and debugging."""
    __tablename__ = "task_executions"
    __table_args__ = {"schema": "earthgazer"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    task_name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    capture_id: Mapped[int | None] = mapped_column(Integer, index=True, default=None)
    status: Mapped[str] = mapped_column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default="now()")
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), default=None)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), default=None)
    duration: Mapped[float | None] = mapped_column(Float, default=None)  # seconds
    result: Mapped[str | None] = mapped_column(String(1000), default=None)
    error: Mapped[str | None] = mapped_column(String(2000), default=None)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    worker_name: Mapped[str | None] = mapped_column(String(255), default=None)


class ProcessingJob(Base):
    """Track multi-task processing jobs (workflows) for high-level monitoring."""
    __tablename__ = "processing_jobs"
    __table_args__ = {"schema": "earthgazer"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "single_capture", "full_pipeline"
    capture_id: Mapped[int | None] = mapped_column(Integer, index=True, default=None)
    status: Mapped[str] = mapped_column(Enum(ProcessingJobStatus), nullable=False, default=ProcessingJobStatus.QUEUED)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default="now()")
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), default=None)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False), default=None)
    total_tasks: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    failed_tasks: Mapped[int] = mapped_column(Integer, default=0)
    job_metadata: Mapped[str | None] = mapped_column(String(2000), default=None)  # JSON string for additional info
