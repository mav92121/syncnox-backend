from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, desc
from datetime import datetime
from app.crud.base import CRUDBase
from app.models.optimization_request import OptimizationRequest, OptimizationStatus
from app.models.route import Route, RouteStop
from app.schemas.optimization import OptimizationRequestCreate


class CRUDOptimizationRequest(CRUDBase[OptimizationRequest, OptimizationRequestCreate, Dict[str, Any]]):
    """
    CRUD operations for OptimizationRequest model.
    
    Extends base CRUD with custom methods for status updates and result storage.
    """
    
    def update_status(
        self,
        db: Session,
        *,
        request_id: int,
        tenant_id: int,
        status: OptimizationStatus,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        error_message: Optional[str] = None
    ) -> Optional[OptimizationRequest]:
        """
        Update the status of an optimization request.
        
        Args:
            db: Database session
            request_id: Optimization request ID
            tenant_id: Tenant ID for isolation
            status: New status
            started_at: Optional start timestamp
            completed_at: Optional completion timestamp
            error_message: Optional error message for failed requests
            
        Returns:
            Updated OptimizationRequest or None if not found
        """
        request = self.get(db=db, id=request_id, tenant_id=tenant_id)
        if not request:
            return None
        
        request.status = status
        if started_at:
            request.started_at = started_at
        if completed_at:
            request.completed_at = completed_at
        if error_message:
            request.error_message = error_message
        
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    
    def store_result(
        self,
        db: Session,
        *,
        request_id: int,
        tenant_id: int,
        result: Dict[str, Any]
    ) -> Optional[OptimizationRequest]:
        """
        Store the optimization result.
        
        Args:
            db: Database session
            request_id: Optimization request ID
            tenant_id: Tenant ID for isolation
            result: Optimization result as JSON
            
        Returns:
            Updated OptimizationRequest or None if not found
        """
        request = self.get(db=db, id=request_id, tenant_id=tenant_id)
        if not request:
            return None
        
        request.result = result
        db.add(request)
        db.commit()
        db.refresh(request)
        return request
    
    def get_with_routes(
        self,
        db: Session,
        *,
        tenant_id: int
    ) -> tuple[List[OptimizationRequest], List[Route]]:
        """
        Fetch optimization requests with routes eagerly loaded.
        
        Returns requests and routes separately to avoid N+1 queries
        while keeping the service layer logic clean.
        
        Args:
            db: Database session
            tenant_id: Tenant ID for isolation
            
        Returns:
            Tuple of (optimization_requests, routes)
        """
        # Fetch optimization requests
        requests = (
            db.query(OptimizationRequest)
            .filter(OptimizationRequest.tenant_id == tenant_id)
            .order_by(desc(OptimizationRequest.created_at))
            .all()
        )
        
        if not requests:
            return [], []
        
        # Fetch routes with eagerly loaded stops and jobs
        request_ids = [r.id for r in requests]
        routes = (
            db.query(Route)
            .options(
                joinedload(Route.stops).joinedload(RouteStop.job)
            )
            .filter(Route.optimization_request_id.in_(request_ids))
            .all()
        )
        
        return requests, routes


# Create singleton instance
optimization_request = CRUDOptimizationRequest(OptimizationRequest)
