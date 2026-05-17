from uuid import UUID, uuid4
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(index=True, unique=True, max_length=2048)
    email_lookup_hash: Optional[str] = Field(default=None, index=True, unique=True, max_length=64)
    phone: str = Field(min_length=7, max_length=2048)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=2048)
    hotel_name: Optional[str] = Field(default=None, max_length=2048)
    country_code: str = Field(default="CO", max_length=2, index=True)
    data_region: str = Field(default="aws-us-east-1", max_length=80, index=True)
    pii_encrypted: bool = Field(default=False)
    pii_key_version: str = Field(default="v1", max_length=16)
    status: int = Field(default=1, ge=0, le=1)
