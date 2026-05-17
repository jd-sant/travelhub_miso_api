from collections.abc import Generator
import logging

import re

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel import select

from adapters.models.user import User
from core.config import settings
from core.privacy import (
    build_lookup_hash,
    decrypt_sensitive_value,
    is_encrypted_sensitive_value,
)

logger = logging.getLogger(__name__)

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
            f"SET search_path TO {_quote_identifier(settings.db_schema)}, public"
        )
        cursor.close()
        dbapi_connection.commit()


def create_db_and_tables() -> None:
    if _is_postgres:
        quoted_schema = _quote_identifier(settings.db_schema)
        with engine.connect() as conn:
            conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {quoted_schema}")
            )
            conn.commit()
    SQLModel.metadata.create_all(engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    if not _is_postgres:
        return
    quoted_schema = _quote_identifier(settings.db_schema)
    quoted_user_table = f"{quoted_schema}.\"user\""
    statements = [
        f"ALTER TABLE IF EXISTS {quoted_user_table} ALTER COLUMN email TYPE VARCHAR(2048)",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ALTER COLUMN phone TYPE VARCHAR(2048)",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ALTER COLUMN full_name TYPE VARCHAR(2048)",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ALTER COLUMN hotel_name TYPE VARCHAR(2048)",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ADD COLUMN IF NOT EXISTS email_lookup_hash VARCHAR(64)",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ADD COLUMN IF NOT EXISTS country_code VARCHAR(2) DEFAULT 'CO'",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ADD COLUMN IF NOT EXISTS data_region VARCHAR(80) DEFAULT 'aws-us-east-1'",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ADD COLUMN IF NOT EXISTS pii_encrypted BOOLEAN DEFAULT FALSE",
        f"ALTER TABLE IF EXISTS {quoted_user_table} ADD COLUMN IF NOT EXISTS pii_key_version VARCHAR(16) DEFAULT 'v1'",
        (
            f"CREATE UNIQUE INDEX IF NOT EXISTS ix_user_email_lookup_hash "
            f"ON {quoted_user_table} (email_lookup_hash) "
            "WHERE email_lookup_hash IS NOT NULL"
        ),
    ]
    with engine.connect() as conn:
        for statement in statements:
            conn.execute(text(statement))
        conn.commit()
    with Session(engine) as session:
        users = session.exec(
            select(User).where(User.email_lookup_hash.is_(None))
        ).all()
        for user in users:
            if is_encrypted_sensitive_value(user.email):
                clear_email = decrypt_sensitive_value(
                    user.email,
                    settings.users_pii_encryption_key,
                )
                if not clear_email:
                    logger.warning(
                        "Skipping email lookup hash backfill for user %s because encrypted email could not be decoded",
                        user.id,
                    )
                    continue
            else:
                clear_email = user.email
            if not clear_email:
                continue
            user.email_lookup_hash = build_lookup_hash(
                clear_email,
                settings.users_email_lookup_hash_secret,
            )
            session.add(user)
        session.commit()


def _quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value}")
    return f'"{value}"'


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
