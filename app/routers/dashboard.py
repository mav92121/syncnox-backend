from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import dashboard_service

router = APIRouter()


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    """
    Get aggregated dashboard data for the current tenant.

    Returns KPI counts, optimization impact metrics,
    recent routes, top drivers, and upcoming schedule.
    """
    return dashboard_service.get_dashboard(db=db, tenant_id=tenant_id)
