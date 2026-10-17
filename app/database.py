
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

load_dotenv(
    Path(__file__).resolve().parent.parent / ".env"
)

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
)


class Base(DeclarativeBase):
    pass


def get_db():
    with Session(engine) as session:
        yield session
