from fastapi import Depends, HTTPException, status, Request
from jose import JWTError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import verify_token
from app.core.config import settings




async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Extract and validate JWT token from Authorization Bearer header, return the authenticated User.
    
    This dependency is optimized for scalability:
    - Uses async database query
    - Preloads tenant relationship in a single query
    - Returns User object with tenant_id readily available
    
    Args:
        request: FastAPI Request to extract Authorization header
        db: Database session
    
    Returns:
        User object with tenant relationship loaded
    
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Extract token from Authorization header
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise credentials_exception
        
        token = authorization.replace("Bearer ", "")
        
        payload = verify_token(token)
        user_id: str = payload.get("id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Efficient query: get user with tenant in one go
    stmt = select(User).where(User.id == int(user_id)).options(selectinload(User.tenant))
    result = db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user
