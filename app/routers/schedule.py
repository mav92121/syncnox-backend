from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.core.tenant_context import get_tenant_id
from app.schemas.schedule import ScheduleResponse
from app.services.schedule import schedule_service

router = APIRouter()


@router.get("/drivers", response_model=ScheduleResponse)
def get_driver_schedule(
    schedule_date: date = Query(..., description="Date to fetch schedule for (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id)
):
    """
    Get schedule blocks for all drivers on a given date.
    
    Returns route assignments and break times for each driver.
    All timestamps are in UTC - frontend should convert to local timezone.
    
    Args:
        schedule_date: The date to fetch schedules for
        
    Returns:
        ScheduleResponse containing all driver schedules
    """
    return schedule_service.get_driver_schedules(
        db=db,
        tenant_id=tenant_id,
        schedule_date=schedule_date
    )
