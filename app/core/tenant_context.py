from fastapi import Depends
from app.models.user import User
from app.dependencies import get_current_user


def get_tenant_id(current_user: User = Depends(get_current_user)) -> int:
    """
    FastAPI dependency that extracts tenant_id from the authenticated user.
    
    This dependency should be added to all routes that need tenant isolation.
    The tenant_id is then passed explicitly through service and CRUD layers.
    
    Args:
        current_user: Authenticated user from JWT token
        
    Returns:
        Tenant ID of the current user
    """
    return current_user.tenant_id
