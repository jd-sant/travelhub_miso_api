from collections.abc import Generator

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

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(
            f"SET search_path TO {settings.db_schema}, public"
        )
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    # Keep explicit model references so SQLModel metadata includes all tables.
    _ = (Reservation, ReservationEvent, ReservationCommandLog)
    if _is_postgres:
        with engine.connect() as conn:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}")
            )
            conn.commit()
    SQLModel.metadata.create_all(engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    with engine.connect() as conn:
        inspector = inspect(conn)
        existing_columns = {
            column["name"] for column in inspector.get_columns(Reservation.__tablename__)
        }
        required_columns = {
            "version": "INTEGER NOT NULL DEFAULT 1",
            "last_policy_snapshot": "TEXT",
            "cancelled_at": "TIMESTAMP",
            "cancellation_reason": "VARCHAR",
        }

        for column_name, column_definition in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(
                text(
                    f"ALTER TABLE {Reservation.__table__.name} "
                    f"ADD COLUMN {column_name} {column_definition}"
                )
            )
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
