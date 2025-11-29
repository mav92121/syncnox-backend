from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
from app.crud.base import CRUDBase
from app.models.optimization_request import OptimizationRequest, OptimizationStatus
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


# Create singleton instance
optimization_request = CRUDOptimizationRequest(OptimizationRequest)
