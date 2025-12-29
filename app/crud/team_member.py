from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.team_member import TeamMember, TeamMemberStatus
from app.schemas.team_member import TeamMemberCreate, TeamMemberUpdate


def _convert_location_to_wkt(data: Dict[str, Any], field_name: str) -> None:
    """Convert a location dict to WKT POINT format in-place."""
    if data.get(field_name):
        loc = data[field_name]
        # GeoAlchemy2 expects WKT format: POINT(x y) -> POINT(lng lat)
        data[field_name] = f"POINT({loc['lng']} {loc['lat']})"


class CRUDTeamMember(CRUDBase[TeamMember, TeamMemberCreate, TeamMemberUpdate]):
    """
    CRUD operations for TeamMember model.
    
    Inherits all standard CRUD operations from CRUDBase and extends with
    custom queries specific to team members.
    """
    
    def create(
        self,
        db: Session,
        *,
        obj_in: TeamMemberCreate,
        tenant_id: int
    ) -> TeamMember:
        """
        Create a new team member with location conversion.
        """
        obj_data = obj_in.model_dump()
        
        # Convert location dicts to WKT strings
        _convert_location_to_wkt(obj_data, "start_location")
        _convert_location_to_wkt(obj_data, "end_location")
        
        db_obj = self.model(tenant_id=tenant_id, **obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: TeamMember,
        obj_in: TeamMemberUpdate | Dict[str, Any]
    ) -> TeamMember:
        """
        Update a team member with location conversion.
        """
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        
        # Convert location dicts to WKT strings
        _convert_location_to_wkt(update_data, "start_location")
        _convert_location_to_wkt(update_data, "end_location")
        
        return super().update(db=db, db_obj=db_obj, obj_in=update_data)
    
    def get_by_email(
        self, 
        db: Session, 
        *, 
        email: str,
        tenant_id: int
    ) -> Optional[TeamMember]:
        """
        Get a team member by email within a tenant.
        
        Args:
            db: Database session
            email: Team member email
            tenant_id: Tenant ID
            
        Returns:
            TeamMember instance or None
        """
        stmt = select(TeamMember).where(
            TeamMember.email == email,
            TeamMember.tenant_id == tenant_id
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    
    def get_by_status(
        self,
        db: Session,
        *,
        status: TeamMemberStatus,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TeamMember]:
        """
        Get team members filtered by status within a tenant.
        
        Args:
            db: Database session
            status: Team member status
            tenant_id: Tenant ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of TeamMember instances
        """
        stmt = select(TeamMember).where(
            TeamMember.status == status,
            TeamMember.tenant_id == tenant_id
        ).offset(skip).limit(limit)
        result = db.execute(stmt)
        return list(result.scalars().all())
    
    def get_by_vehicle(
        self,
        db: Session,
        *,
        vehicle_id: int,
        tenant_id: int
    ) -> Optional[TeamMember]:
        """
        Get team member assigned to a specific vehicle.
        
        Args:
            db: Database session
            vehicle_id: Vehicle ID
            tenant_id: Tenant ID
            
        Returns:
            TeamMember instance or None
        """
        stmt = select(TeamMember).where(
            TeamMember.vehicle_id == vehicle_id,
            TeamMember.tenant_id == tenant_id
        )
        result = db.execute(stmt)
        return result.scalar_one_or_none()
    
    def get_multi_by_ids(
        self,
        db: Session,
        *,
        ids: List[int],
        tenant_id: int
    ) -> List[TeamMember]:
        """
        Bulk fetch team members by IDs.
        
        Args:
            db: Database session
            ids: List of team member IDs to fetch
            tenant_id: Tenant ID for isolation
            
        Returns:
            List of TeamMember instances
        """
        stmt = select(TeamMember).where(
            TeamMember.id.in_(ids),
            TeamMember.tenant_id == tenant_id
        )
        result = db.execute(stmt)
        return list(result.scalars().all())


# Create a singleton instance
team_member = CRUDTeamMember(TeamMember)
