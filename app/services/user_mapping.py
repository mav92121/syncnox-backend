from sqlalchemy.orm import Session
from typing import Optional, Dict
from app.crud.user_mapping import user_mapping_crud
from app.models.user_column_mapping import UserColumnMapping
from app.core.logging_config import logger


class UserMappingService:
    """Service for managing user column mapping preferences"""
    
    def get_default_mapping(
        self, 
        db: Session,
        tenant_id: int, 
        entity_type: str
    ) -> Optional[Dict[str, str]]:
        """
        Get user's saved default mapping for an entity type
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            entity_type: Entity type (e.g., "job")
            
        Returns:
            Mapping configuration dict or None
        """
        mapping = user_mapping_crud.get_by_tenant_and_type(db, tenant_id, entity_type)
        if mapping:
            logger.info(f"Loaded default mapping for tenant={tenant_id}, entity={entity_type}")
            return mapping.mapping_config
        return None
    
    def save_mapping(
        self,
        db: Session,
        tenant_id: int,
        entity_type: str,
        mapping_config: Dict[str, str]
    ) -> UserColumnMapping:
        """
        Save or update user's default mapping
        
        Args:
            db: Database session
            tenant_id: Tenant ID
            entity_type: Entity type (e.g., "job")
            mapping_config: Mapping configuration {identifier: excel_column}
            
        Returns:
            Created or updated UserColumnMapping
        """
        return user_mapping_crud.create_or_update(
            db=db,
            tenant_id=tenant_id,
            entity_type=entity_type,
            mapping_config=mapping_config
        )


user_mapping_service = UserMappingService()
