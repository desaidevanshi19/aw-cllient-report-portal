import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./portal.db")

if DATABASE_URL.startswith("sqlite"):
    # Extract the file path from the URL and ensure its directory exists.
    # e.g. sqlite:////data/portal.db  →  /data/portal.db
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path:  # not an in-memory DB
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
