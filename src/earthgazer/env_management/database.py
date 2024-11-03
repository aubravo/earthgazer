from sqlmodel import SQLModel, create_engine

from earthgazer.objects import *  # noqa: F403 - Importing all objects to create the database

engine = create_engine("sqlite:///earthgazer.db")
SQLModel.metadata.create_all(engine)
