from collections.abc import Generator
import re

from sqlalchemy import event, text
from sqlmodel import SQLModel, Session, create_engine

from core.config import settings

_is_postgres = settings.database_url.startswith("postgresql")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    connect_args=connect_args,
)

if _is_postgres:

    _SCHEMA_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def _validated_schema_name() -> str:
        schema_name = settings.db_schema.strip()
        if not _SCHEMA_IDENTIFIER_RE.fullmatch(schema_name):
            raise RuntimeError(
                "DB_SCHEMA debe ser un identificador SQL valido para el schema de notifications."
            )
        return schema_name

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        schema_name = _validated_schema_name()
        cursor = dbapi_connection.cursor()
        cursor.execute(f'SET search_path TO "{schema_name}", public')
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        schema_name = _validated_schema_name()
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            conn.commit()
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
