from sqlalchemy.orm import Session
from typing import Optional, Dict
from app.models.user_column_mapping import UserColumnMapping
from app.core.logging_config import logger


class UserMappingCRUD:
    """CRUD operations for UserColumnMapping"""
    
    def get_by_tenant_and_type(
        self, 
        db: Session, 
        tenant_id: int, 
        entity_type: str
    ) -> Optional[UserColumnMapping]:
        """Get user's saved mapping for specific entity type"""
        return db.query(UserColumnMapping).filter(
            UserColumnMapping.tenant_id == tenant_id,
            UserColumnMapping.entity_type == entity_type
        ).first()
    
    def create_or_update(
        self,
        db: Session,
        tenant_id: int,
        entity_type: str,
        mapping_config: Dict[str, str]
    ) -> UserColumnMapping:
        """Create or update user's default mapping"""
        existing = self.get_by_tenant_and_type(db, tenant_id, entity_type)
        
        if existing:
            existing.mapping_config = mapping_config
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated mapping for tenant={tenant_id}, entity={entity_type}")
            return existing
        else:
            new_mapping = UserColumnMapping(
                tenant_id=tenant_id,
                entity_type=entity_type,
                mapping_config=mapping_config
            )
            db.add(new_mapping)
            db.commit()
            db.refresh(new_mapping)
            logger.info(f"Created mapping for tenant={tenant_id}, entity={entity_type}")
            return new_mapping


user_mapping_crud = UserMappingCRUD()
