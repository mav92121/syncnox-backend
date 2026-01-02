from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.onboarding import Onboarding
from app.schemas.onboarding import BasicInfoRequest


class CRUDOnboarding:
    """CRUD operations for Onboarding model."""

    def get_by_tenant_id(self, db: Session, tenant_id: int) -> Onboarding:
        """
        Get onboarding record for a tenant, creating one if it doesn't exist.
        """
        result = db.execute(
            select(Onboarding).where(Onboarding.tenant_id == tenant_id)
        )
        onboarding = result.scalar_one_or_none()
        
        if not onboarding:
            # Create new onboarding record
            onboarding = Onboarding(
                tenant_id=tenant_id,
                is_completed=False,
                current_step=0
            )
            db.add(onboarding)
            db.commit()
            db.refresh(onboarding)
        
        return onboarding

    def update_basic_info(
        self, 
        db: Session, 
        tenant_id: int, 
        data: BasicInfoRequest
    ) -> Onboarding:
        """
        Update company name and industry, and advance to step 2.
        """
        onboarding = self.get_by_tenant_id(db, tenant_id)
        onboarding.company_name = data.company_name
        onboarding.industry = data.industry.value
        onboarding.current_step = 2  # Advance to depot step
        db.commit()
        db.refresh(onboarding)
        return onboarding

    def advance_step(self, db: Session, tenant_id: int, step: int) -> Onboarding:
        """
        Advance to a specific step.
        """
        onboarding = self.get_by_tenant_id(db, tenant_id)
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
        onboarding.current_step = 5  # Beyond last step
        db.commit()
        db.refresh(onboarding)
        return onboarding


# Create singleton instance
onboarding = CRUDOnboarding()
