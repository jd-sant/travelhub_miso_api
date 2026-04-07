from uuid import UUID
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    email: EmailStr
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=100)
    hotel_name: Optional[str] = Field(default=None, max_length=100)
    role: str = Field(default="traveler")
    status: int = Field(default=1, ge=0, le=1)


class UserResponse(BaseModel):
    id: UUID
    email: str
    phone: str
    full_name: str
    hotel_name: Optional[str]
    status: int


class UserCredentialsData(BaseModel):
    id: UUID
    email: str
    password: str
    status: int
    roles: list[str]


class VerifyCredentialsRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class VerifyCredentialsResponse(BaseModel):
    id: UUID
    email: str
    status: int
    roles: list[str]
