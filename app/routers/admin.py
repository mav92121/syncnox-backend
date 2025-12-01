from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import get_password_hash
from app.core.config import settings

router = APIRouter()


class TenantInviteRequest(BaseModel):
    business_name: str
    email: EmailStr
    password: str


class TenantInviteResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    user_id: int
    user_email: str


def verify_admin_key(api_key_header: str = Header(...)):
    """Verify the admin API key from the request header."""
    if api_key_header != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin API key"
        )


@router.post("/tenant/invite", response_model=TenantInviteResponse)
def create_tenant(
    request: TenantInviteRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key)
):
    """
    Create a new tenant and its initial admin user.
    
    Protected by x-admin-key header.
    
    Args:
        request: Business name, email, and password for the new tenant
        db: Database session
    
    Returns:
        Created tenant and user information
    
    Raises:
        HTTPException: If email already exists
    """
    # Check if user with this email already exists
    stmt = select(User).where(User.email == request.email)
    existing_user = db.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create tenant
    tenant = Tenant(name=request.business_name)
    db.add(tenant)
    db.flush()  # Get tenant.id without committing
    
    # Create user
    user = User(
        email=request.email,
        hashed_password=get_password_hash(request.password),
        tenant_id=tenant.id,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(tenant)
    db.refresh(user)
    
    return TenantInviteResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        user_id=user.id,
        user_email=user.email
    )
