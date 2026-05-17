from uuid import UUID

from sqlmodel import Field, SQLModel


class UserRole(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    role_id: UUID = Field(foreign_key="role.id", primary_key=True)
