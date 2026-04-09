import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost:5432/travelhub"
)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"options": "-c search_path=properties_schema"}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session
)


def get_session() -> Session:
    """Dependency to get database session"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_db_and_tables():
    """Create database tables and seed with initial data"""
    SQLModel.metadata.create_all(engine)
    
    # Seed database if empty
    from db.seed import seed_properties_if_empty
    with Session(engine) as session:
        seed_properties_if_empty(session)

