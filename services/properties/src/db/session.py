from collections.abc import Generator

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

from adapters.models import Property, PropertyCancellationPolicy, PropertyImage, PropertyReview
from core.config import settings
from db.seed import sync_demo_properties_seed

_is_postgres = settings.database_url.startswith("postgresql")


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {"client_encoding": "utf8"}
)

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=connect_args,
)

if _is_postgres:

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET search_path TO {settings.db_schema}, public")
        cursor.execute("SET client_encoding TO 'UTF8'")
        if hasattr(dbapi_connection, 'set_client_encoding'):
            dbapi_connection.set_client_encoding('UTF8')
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        with engine.connect() as conn:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}")
            )
            conn.commit()
    _ = (Property, PropertyCancellationPolicy, PropertyImage, PropertyReview)
    SQLModel.metadata.create_all(engine)

    # Create or sync demo properties and assets only in allowed environments.
    if settings.seed_demo_data:
        with Session(engine) as session:
            sync_demo_properties_seed(session)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
