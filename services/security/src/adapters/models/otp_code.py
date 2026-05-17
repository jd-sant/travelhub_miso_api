from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class OtpCode(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(index=True)
    email: str = Field(index=True)
    code: str = Field(max_length=128)
    roles: str = Field(default="")  # comma-separated roles
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime
    is_used: bool = Field(default=False)
    attempts: int = Field(default=0)
