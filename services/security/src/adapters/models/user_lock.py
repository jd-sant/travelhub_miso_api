from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class UserLock(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(unique=True, index=True)
    locked_until: datetime
