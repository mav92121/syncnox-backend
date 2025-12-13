from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User
from app.core.security import get_password_hash


class CRUDUser:
    """
    CRUD operations for User model.
    
    Note: User model doesn't have tenant_id (it references Tenant),
    so we don't inherit from CRUDBase.
    """
    
    def __init__(self):
        self.model = User
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Retrieve user by email address.
        
        Args:
            db: Database session
            email: User email
            
        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.email == email)
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    
    def get(self, db: Session, user_id: int) -> Optional[User]:
        """
        Retrieve user by ID.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.id == user_id)
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    
    def create(
        self,
        db: Session,
        *,
        email: str,
        password: str,
        tenant_id: int,
        is_active: bool = True
    ) -> User:
        """
        Create a new user with hashed password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password (will be hashed)
            tenant_id: Tenant ID the user belongs to
            is_active: Whether user is active
            
        Returns:
            Created User instance
        """
        hashed_password = get_password_hash(password)
        db_user = User(
            email=email,
            hashed_password=hashed_password,
            tenant_id=tenant_id,
            is_active=is_active
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user


# Create singleton instance
user = CRUDUser()
