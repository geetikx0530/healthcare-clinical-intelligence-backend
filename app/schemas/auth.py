from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    name: str = Field(..., description="Full user name")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Password (minimum 6 characters)")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        if isinstance(v, str):
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Name cannot be empty or whitespace only")
            return trimmed
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
