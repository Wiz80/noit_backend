from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: Optional[str] = None  # Optional for Google OAuth users
    google_id: Optional[str] = None
    profile_picture: Optional[str] = None

class UserUpdate(UserBase):
    password: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None

class UserInDBBase(UserBase):
    id: str
    is_active: bool
    is_superuser: bool
    google_id: Optional[str] = None
    full_name: Optional[str] = None
    profile_picture: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    hashed_password: Optional[str] = None