from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.core.logging_config import logger
from app.schemas.bulk_upload import UserMappingCreate, UserMappingResponse
from app.services.user_mapping import user_mapping_service


router = APIRouter()


@router.get("/{entity_type}", response_model=UserMappingResponse)
def get_user_mapping(
    entity_type: str,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Get user's saved default column mapping for an entity type
    
    Args:
        entity_type: Entity type (e.g., "job", "team_member")
        
    Returns:
        UserMappingResponse with saved mapping config or 404
    """
    try:
        mapping_config = user_mapping_service.get_default_mapping(
            db=db,
            tenant_id=tenant_id,
            entity_type=entity_type
        )
        
        if not mapping_config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No default mapping found for entity type '{entity_type}'"
            )
        
        # Get the full mapping object to return
        from app.crud.user_mapping import user_mapping_crud
        mapping = user_mapping_crud.get_by_tenant_and_type(db, tenant_id, entity_type)
        
        return mapping
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user mapping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve mapping: {str(e)}"
        )


@router.post("", response_model=UserMappingResponse, status_code=status.HTTP_201_CREATED)
def save_user_mapping(
    mapping_data: UserMappingCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Save or update user's default column mapping
    
    Args:
        mapping_data: Mapping configuration to save
        
    Returns:
        Created or updated UserMappingResponse
    """
    try:
        mapping = user_mapping_service.save_mapping(
            db=db,
            tenant_id=tenant_id,
            entity_type=mapping_data.entity_type,
            mapping_config=mapping_data.mapping_config
        )
        
        return mapping
        
    except Exception as e:
        logger.error(f"Error saving user mapping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save mapping: {str(e)}"
        )
