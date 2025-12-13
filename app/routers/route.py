from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.schemas.route import RouteAnalyticsItem
from app.services.route_analytics import route_analytics_service

router = APIRouter()

@router.get("", response_model=List[RouteAnalyticsItem])
def get_routes_analytics(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Get aggregated analytics for all routes (optimization plans).
    
    Returns high-level route details including:
    - Integrated metrics (Total Distance, Time)
    - Optimization Status
    - Progress Percentage & Stop Counts
    - Assigned Team Members
    """
    return route_analytics_service.get_all_routes_analytics(db, tenant_id)
