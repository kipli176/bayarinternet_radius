from pydantic import BaseModel, EmailStr
from datetime import datetime, date
from typing import Optional
from uuid import UUID


class UserBase(BaseModel):
    username: str
    full_name: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str]
    alamat: Optional[str]   # ✅ sesuai DB
    profile_id: UUID


class UserCreate(UserBase):
    password: str
    active_until: Optional[date]


class UserUpdate(BaseModel):
    password: Optional[str]
    profile_id: Optional[UUID]
    full_name: Optional[str]
    email: Optional[EmailStr]
    phone: Optional[str]
    alamat: Optional[str]   # ✅ bisa diupdate
    status: Optional[str]   # active, suspended, expired
    active_until: Optional[date]


class UserResponse(UserBase):
    id: UUID
    status: str
    active_until: Optional[date]
    created_at: datetime

    class Config:
        orm_mode = True
