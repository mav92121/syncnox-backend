from typing import List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.crud import team_member as team_member_crud
from app.schemas.team_member import TeamMemberCreate, TeamMemberUpdate
from app.models.team_member import TeamMember
from app.core.tenant_context import get_tenant_id


class TeamMemberService:
    """
    Service layer for team member business logic.
    
    This layer handles business rules, validation, and coordination
    of CRUD operations.
    """
    
    def __init__(self):
        self.crud = team_member_crud
    
    def get_team_member(
        self,
        db: Session,
        team_member_id: int,
        tenant_id: int
    ) -> TeamMember:
        """
        Get a team member by ID with tenant isolation.
        
        Args:
            db: Database session
            team_member_id: Team member ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            TeamMember instance
            
        Raises:
            HTTPException 404: If team member not found
        """
        team_member = self.crud.get(db=db, id=team_member_id, tenant_id=tenant_id)
        
        if not team_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )
        
        return team_member
    
    def get_team_members(
        self,
        db: Session,
        tenant_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TeamMember]:
        """
        Get all team members with tenant isolation.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of TeamMember instances
        """
        return self.crud.get_multi(db=db, skip=skip, limit=limit, tenant_id=tenant_id)
    
    def create_team_member(
        self,
        db: Session,
        team_member_data: TeamMemberCreate,
        tenant_id: int
    ) -> TeamMember:
        """
        Create a new team member with business validation.
        
        Args:
            db: Database session
            team_member_data: Team member creation data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Created TeamMember instance
            
        Raises:
            HTTPException 400: If email already exists for this tenant
        """
        # Business rule: Check if email is unique within tenant
        if team_member_data.email:
            existing_member = self.crud.get_by_email(
                db=db,
                email=team_member_data.email,
                tenant_id=tenant_id
            )
            if existing_member:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team member with this email already exists"
                )
        
        # Create the team member
        return self.crud.create(db=db, obj_in=team_member_data, tenant_id=tenant_id)
    
    def update_team_member(
        self,
        db: Session,
        team_member_id: int,
        team_member_data: TeamMemberUpdate,
        tenant_id: int
    ) -> TeamMember:
        """
        Update a team member with business validation.
        
        Args:
            db: Database session
            team_member_id: Team member ID
            team_member_data: Team member update data
            tenant_id: Tenant ID for isolation
            
        Returns:
            Updated TeamMember instance
            
        Raises:
            HTTPException 404: If team member not found
            HTTPException 400: If email already exists for this tenant
        """
        # Get existing team member
        team_member = self.get_team_member(db=db, team_member_id=team_member_id, tenant_id=tenant_id)
        
        # Business rule: Check if new email is unique within tenant
        if team_member_data.email and team_member_data.email != team_member.email:
            existing_member = self.crud.get_by_email(
                db=db,
                email=team_member_data.email,
                tenant_id=tenant_id
            )
            if existing_member:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Team member with this email already exists"
                )
        
        # Update the team member
        return self.crud.update(db=db, db_obj=team_member, obj_in=team_member_data)
    
    def delete_team_member(
        self,
        db: Session,
        team_member_id: int,
        tenant_id: int
    ) -> None:
        """
        Delete a team member.
        
        Args:
            db: Database session
            team_member_id: Team member ID
            tenant_id: Tenant ID for isolation
            
        Raises:
            HTTPException 404: If team member not found
        """
        deleted = self.crud.delete(db=db, id=team_member_id, tenant_id=tenant_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Team member not found"
            )


# Create a singleton instance
team_member_service = TeamMemberService()
