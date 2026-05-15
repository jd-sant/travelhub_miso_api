from collections.abc import Generator
import re

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

from adapters.models import Property, PropertyCancellationPolicy, PropertyImage, PropertyReview
from core.config import settings
from db.seed import sync_demo_properties_seed

_is_postgres = settings.database_url.startswith("postgresql")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quoted_identifier(identifier: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Invalid database schema name: {identifier!r}")
    return f'"{identifier}"'


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
        del connection_record
        cursor = dbapi_connection.cursor()
        quoted_schema = _quoted_identifier(settings.db_schema)
        cursor.execute(f"SET search_path TO {quoted_schema}, public")
        cursor.execute("SET client_encoding TO 'UTF8'")
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        with engine.connect() as conn:
            quoted_schema = _quoted_identifier(settings.db_schema)
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
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
