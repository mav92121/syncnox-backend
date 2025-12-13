from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.crud.base import CRUDBase
from app.models.team_member import TeamMember, TeamMemberStatus
from app.schemas.team_member import TeamMemberCreate, TeamMemberUpdate


class CRUDTeamMember(CRUDBase[TeamMember, TeamMemberCreate, TeamMemberUpdate]):
    """
    CRUD operations for TeamMember model.
    
    Inherits all standard CRUD operations from CRUDBase and extends with
    custom queries specific to team members.
    """
    
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
