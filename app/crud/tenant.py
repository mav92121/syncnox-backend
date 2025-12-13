from typing import Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.tenant import Tenant
from app.models.user import User
from app.crud.user import user as user_crud


class CRUDTenant:
    """
    CRUD operations for Tenant model.
    
    Note: Tenant model doesn't have tenant_id (it IS the tenant),
    so we don't inherit from CRUDBase.
    """
    
    def __init__(self):
        self.model = Tenant
    
    def create_with_user(
        self,
        db: Session,
        *,
        business_name: str,
        email: str,
        password: str
    ) -> Tuple[Tenant, User]:
        """
        Create a tenant and its initial admin user atomically.
        
        This method handles the transaction atomicity for creating
        both tenant and user records together.
        
        Args:
            db: Database session
            business_name: Tenant business name
            email: Admin user email
            password: Admin user password (will be hashed)
            
        Returns:
            Tuple of (created Tenant, created User)
            
        Raises:
            ValueError: If user with this email already exists
        """
        try:
            # Create tenant
            tenant = Tenant(name=business_name)
            db.add(tenant)
            db.flush()  # Get tenant.id without committing
            
            # Create user using CRUD method without committing
            user = user_crud.create(
                db=db,
                email=email,
                password=password,
                tenant_id=tenant.id,
                is_active=True,
                commit=False  # Don't commit yet - we'll commit both together
            )
            
            # Commit both tenant and user atomically
            db.commit()
            db.refresh(tenant)
            db.refresh(user)
            
            return tenant, user
            
        except IntegrityError as e:
            db.rollback()
            # Check if error is due to duplicate email
            if "user_email_key" in str(e) or "unique constraint" in str(e).lower():
                raise ValueError(f"User with email {email} already exists")
            raise e


# Create singleton instance
tenant = CRUDTenant()
