from typing import Tuple
from sqlalchemy.orm import Session
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
            Exception: If user email already exists (handled by caller)
        """
        # Create tenant
        tenant = Tenant(name=business_name)
        db.add(tenant)
        db.flush()  # Get tenant.id without committing
        
        # Create user using CRUD method
        user = user_crud.create(
            db=db,
            email=email,
            password=password,
            tenant_id=tenant.id,
            is_active=True
        )
        
        # User creation already commits, so we just need to refresh tenant
        db.refresh(tenant)
        
        return tenant, user


# Create singleton instance
tenant = CRUDTenant()
