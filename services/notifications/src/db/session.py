from collections.abc import Generator
import re

from sqlalchemy import event, inspect, text
from sqlmodel import SQLModel, Session, create_engine

from adapters.models.notification import Notification
from core.config import settings

_is_postgres = settings.database_url.startswith("postgresql")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {"client_encoding": "utf8"}

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
        cursor.execute("SET client_encoding TO 'UTF8'")
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        schema_name = _validated_schema_name()
        with engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            conn.commit()
    SQLModel.metadata.create_all(engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    with engine.connect() as conn:
        schema_name = _validated_schema_name() if _is_postgres else None
        inspector = inspect(conn)
        inspection_schema = schema_name if _is_postgres else None
        columns = {
            column["name"]: column
            for column in inspector.get_columns(
                Notification.__tablename__,
                schema=inspection_schema,
            )
        }

        payment_id_column = columns.get("payment_id")
        if not payment_id_column:
            return
        if payment_id_column.get("nullable", True):
            return
        if not _is_postgres:
            return

        conn.execute(
            text(
                f'ALTER TABLE "{schema_name}"."{Notification.__table__.name}" '
                "ALTER COLUMN payment_id DROP NOT NULL"
            )
        )
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
