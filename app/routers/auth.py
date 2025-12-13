from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.core.security import verify_password, create_access_token
from app.crud.user import user as user_crud

router = APIRouter()


class VerifyCredentialsRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyCredentialsResponse(BaseModel):
    user: dict
    access_token: str


@router.post("/verify-credentials", response_model=VerifyCredentialsResponse)
def verify_credentials(credentials: VerifyCredentialsRequest, db: Session = Depends(get_db)):
    """
    Verify user credentials for NextAuth.
    
    This endpoint is used by NextAuth to validate credentials during login.
    It does NOT create or manage sessions - that's handled by NextAuth.
    
    Args:
        credentials: Email and password
        db: Database session
    
    Returns:
        User info if credentials are valid
    
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email using CRUD
    user = user_crud.get_by_email(db, email=credentials.email)
    
    # Validate credentials
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    # Generate JWT access token with user claims
    access_token = create_access_token(
        data={
            "id": str(user.id),
            "email": user.email,
            "tenant_id": user.tenant_id,
        }
    )
    
    return VerifyCredentialsResponse(
        user={
            "id": str(user.id),
            "email": user.email,
            "tenant_id": user.tenant_id,
        },
        access_token=access_token
    )
