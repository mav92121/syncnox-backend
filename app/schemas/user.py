from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True

class UserCreate(UserBase):
    password: str
    tenant_id: int

class UserResponse(UserBase):
    id: int
    tenant_id: int

    class Config:
        from_attributes = True
