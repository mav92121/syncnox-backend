from pydantic import BaseModel
from typing import Optional

class TenantBase(BaseModel):
    name: str
    plan_type: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    plan_type: Optional[str] = None

class TenantResponse(TenantBase):
    id: int

    class Config:
        from_attributes = True
