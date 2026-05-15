from collections.abc import Generator
import re

from sqlalchemy import event, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from adapters import models  # noqa: F401
from core.config import settings

_is_postgres = settings.database_url.startswith("postgresql")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(identifier: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Invalid database schema name: {identifier!r}")
    return f'"{identifier}"'


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {"client_encoding": "utf8"}
)

engine_kwargs = {
    "echo": settings.db_echo,
    "connect_args": connect_args,
}

if settings.database_url == "sqlite://":
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, **engine_kwargs)

if _is_postgres:

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        del connection_record
        cursor = dbapi_connection.cursor()
        quoted_schema = _quote_identifier(settings.db_schema)
        cursor.execute(f"SET search_path TO {quoted_schema}, public")
        cursor.execute("SET client_encoding TO 'UTF8'")
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        with engine.connect() as conn:
            quoted_schema = _quote_identifier(settings.db_schema)
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}"))
            conn.commit()
    SQLModel.metadata.create_all(engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    if not _is_postgres:
        return
    quoted_schema = _quote_identifier(settings.db_schema)
    statements = [
        f"ALTER TABLE IF EXISTS {quoted_schema}.pricing_change_log ADD COLUMN IF NOT EXISTS actor_ip VARCHAR(120)",
        f"ALTER TABLE IF EXISTS {quoted_schema}.pricing_change_log ADD COLUMN IF NOT EXISTS request_checksum VARCHAR(64)",
    ]
    with engine.connect() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
