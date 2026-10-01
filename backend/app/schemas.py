from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["client", "operator", "admin"]
Status = Literal["submitted", "in_progress", "delivered", "accepted", "rejected"]


def _check_bcrypt_length(value: str) -> str:
    if len(value.encode()) > 72:
        raise ValueError("password must be at most 72 bytes")
    return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    role: Role
    organisation: str | None
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)
    role: Role
    organisation: str | None = Field(default=None, max_length=255)

    _pw = field_validator("password")(_check_bcrypt_length)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: Role | None = None
    is_active: bool | None = None