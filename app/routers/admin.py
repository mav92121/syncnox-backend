from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.core.config import settings
from app.crud.tenant import tenant as tenant_crud
from app.crud.user import user as user_crud

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
    existing_user = user_crud.get_by_email(db, email=request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Create tenant and user atomically
    tenant, user = tenant_crud.create_with_user(
        db=db,
        business_name=request.business_name,
        email=request.email,
        password=request.password
    )
    
    return TenantInviteResponse(
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        user_id=user.id,
        user_email=user.email
    )
