from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str


class OtpVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=6, max_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class TokenValidationRequest(BaseModel):
    token: str


class TokenValidationResponse(BaseModel):
    user_id: UUID
    email: str
    role: str
    valid: bool


class UserCredentials(BaseModel):
    id: UUID
    email: str
    status: int
    roles: list[str]


class OtpRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: str
    code: str
    roles: str
    attempts: int


class UserLockRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    locked_until: datetime
