from collections.abc import Generator
import re

from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine

from adapters.models import Reservation, ReservationCommandLog, ReservationEvent
from core.config import settings

_is_postgres = settings.database_url.startswith("postgresql")

connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

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
                "DB_SCHEMA debe ser un identificador SQL valido para el schema de reservations."
            )
        return schema_name

    def _quoted_identifier(identifier: str) -> str:
        return f'"{identifier}"'

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        schema_name = _validated_schema_name()
        cursor = dbapi_connection.cursor()
        cursor.execute(
            f"SET search_path TO {_quoted_identifier(schema_name)}, public"
        )
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    # Keep explicit model references so SQLModel metadata includes all tables.
    _ = (Reservation, ReservationEvent, ReservationCommandLog)
    if _is_postgres:
        schema_name = _validated_schema_name()
        with engine.connect() as conn:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {_quoted_identifier(schema_name)}")
            )
            conn.commit()
    SQLModel.metadata.create_all(engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    with engine.connect() as conn:
        schema_name = _validated_schema_name() if _is_postgres else None
        inspector = inspect(conn)
        inspection_schema = schema_name if _is_postgres else None
        existing_columns = {
            column["name"]
            for column in inspector.get_columns(
                Reservation.__tablename__, schema=inspection_schema
            )
        }
        required_columns = {
            "version": "INTEGER NOT NULL DEFAULT 1",
            "last_policy_snapshot": "TEXT",
            "cancelled_at": "TIMESTAMP",
            "cancellation_reason": "VARCHAR",
        }

        table_name = (
            f'{_quoted_identifier(schema_name)}.{_quoted_identifier(Reservation.__table__.name)}'
            if _is_postgres
            else Reservation.__table__.name
        )

        for column_name, column_definition in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(
                text(
                    f"ALTER TABLE {table_name} "
                    f"ADD COLUMN {column_name} {column_definition}"
                )
            )
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
