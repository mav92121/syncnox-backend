from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException, status
from app.models.onboarding import Onboarding
from app.schemas.onboarding import BasicInfoRequest


# Step constants
STEP_WELCOME = 0
STEP_BASIC_INFO = 1
STEP_DEPOT = 2
STEP_FLEET = 3
STEP_TEAM = 4
STEP_COMPLETE = 5


class CRUDOnboarding:
    """CRUD operations for Onboarding model."""

    def get_by_tenant_id(self, db: Session, tenant_id: int) -> Onboarding:
        """
        Get onboarding record for a tenant, creating one if it doesn't exist.
        Uses PostgreSQL INSERT...ON CONFLICT DO NOTHING to avoid race conditions.
        Does NOT commit - leaves transaction control to callers.
        """
        # Use PostgreSQL upsert: INSERT ... ON CONFLICT DO NOTHING
        # This is atomic and race-condition safe
        stmt = pg_insert(Onboarding).values(
            tenant_id=tenant_id,
            is_completed=False,
            current_step=STEP_WELCOME
        ).on_conflict_do_nothing(index_elements=['tenant_id'])
        
        db.execute(stmt)
        db.flush()  # Flush to ensure insert is visible, but don't commit
        
        # Now select the record (either existing or just inserted)
        result = db.execute(
            select(Onboarding).where(Onboarding.tenant_id == tenant_id)
        )
        onboarding = result.scalar_one()
        
        return onboarding

    def update_basic_info(
        self, 
        db: Session, 
        tenant_id: int, 
        data: BasicInfoRequest
    ) -> Onboarding:
        """
        Update company name and industry, and advance to depot step.
        """
        onboarding = self.get_by_tenant_id(db, tenant_id)
        onboarding.company_name = data.company_name
        onboarding.industry = data.industry.value
        # Only advance if not already past this step
        if onboarding.current_step < STEP_DEPOT:
            onboarding.current_step = STEP_DEPOT
        db.commit()
        db.refresh(onboarding)
        return onboarding

    def advance_step(self, db: Session, tenant_id: int, step: int) -> Onboarding:
        """
        Advance to a specific step. Only allows forward progression within valid range.
        
        Raises:
            HTTPException: If step is invalid (not in range 0-5) or would go backwards
        """
        # Validate step range
        if step < STEP_WELCOME or step > STEP_COMPLETE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid step value: {step}. Must be between {STEP_WELCOME} and {STEP_COMPLETE}"
            )
        
        onboarding = self.get_by_tenant_id(db, tenant_id)
        
        # Validate forward progression
        if step <= onboarding.current_step:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot go backwards. Current step: {onboarding.current_step}, requested: {step}"
            )
        
        onboarding.current_step = step
        db.commit()
        db.refresh(onboarding)
        return onboarding

    def complete_onboarding(self, db: Session, tenant_id: int) -> Onboarding:
        """
        Mark onboarding as completed.
        """
        onboarding = self.get_by_tenant_id(db, tenant_id)
        onboarding.is_completed = True
        onboarding.current_step = STEP_COMPLETE
        db.commit()
        db.refresh(onboarding)
        return onboarding


# Create singleton instance
onboarding = CRUDOnboarding()

