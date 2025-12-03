from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.config import settings

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str
    user: dict


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Authenticate user and set HTTP-only cookie with JWT token.
    
    The token contains:
    - id: user_id
    - tenant_id: tenant_id
    
    Args:
        credentials: Email and password
        response: FastAPI Response to set cookies
        db: Database session
    
    Returns:
        Success message and user info (token stored in HTTP-only cookie)
    
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    stmt = select(User).where(User.email == credentials.email)
    result = db.execute(stmt)
    user = result.scalar_one_or_none()
    
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
    
    # Create JWT token with user_id and tenant_id
    access_token = create_access_token(
        data={"id": str(user.id), "tenant_id": user.tenant_id, "email": user.email}
    )
    
    # Set HTTP-only cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=access_token,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.cookie_max_age,
        domain=".syncnox.com"
    )
    
    return LoginResponse(
        message="Login successful",
        user={
            "id": str(user.id),
            "email": user.email,
            "tenant_id": user.tenant_id,
        }
    )


@router.post("/logout")
def logout(response: Response):
    """
    Clear authentication cookie to log out user.
    
    Args:
        response: FastAPI Response to clear cookies
    
    Returns:
        Success message
    """
    # Clear the authentication cookie
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value="",
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=0,  # Expire immediately
        domain=".syncnox.com"
    )
    
    return {"message": "Logout successful"}
