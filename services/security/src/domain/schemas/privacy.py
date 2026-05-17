from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SensitiveDataAuditRequest(BaseModel):
    actor_user_id: UUID | None = None
    action: str = Field(min_length=3, max_length=80)
    resource_type: str = Field(min_length=2, max_length=80)
    resource_id: str | None = Field(default=None, max_length=120)
    pii_fields: list[str] = Field(default_factory=list)
    source_ip: str = Field(default="unknown", min_length=1, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SensitiveDataAuditResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    pii_fields: list[str]
    source_ip: str
    country_code: str | None
    data_region: str
    previous_hash: str | None
    entry_hash: str
    created_at: datetime


class DataResidencyPolicyResponse(BaseModel):
    country_code: str
    data_region: str
    storage_policy: str
