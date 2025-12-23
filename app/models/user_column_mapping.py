from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base, TimestampMixin


class UserColumnMapping(Base, TimestampMixin):
    """
    Stores user's default column mapping preferences for bulk uploads.
    
    This allows users to save their preferred column mappings and automatically
    apply them to future uploads of the same entity type.
    """
    __tablename__ = "user_column_mapping"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)
    entity_type = Column(String, nullable=False)  # "job", "team_member", etc.
    mapping_config = Column(JSONB, nullable=False)  # {"column_identifier": "excel_header"}

    __table_args__ = (
        UniqueConstraint('tenant_id', 'entity_type', name='uix_tenant_entity_mapping'),
    )
