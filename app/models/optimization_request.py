from sqlalchemy import Column, Integer, String, ForeignKey, Date, DateTime, Text, Enum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
import enum
from app.database import Base, TimestampMixin


class OptimizationGoal(str, enum.Enum):
    """Optimization goal for route planning."""
    MINIMUM_TIME = "minimum_time"
    MINIMUM_DISTANCE = "minimum_distance"


class OptimizationStatus(str, enum.Enum):
    """Status of optimization request."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OptimizationRequest(Base, TimestampMixin):
    """
    Optimization request model for route optimization jobs.
    
    Stores the request parameters, status, and results of optimization runs.
    Designed to work with ProcessPoolExecutor and easily migrate to Celery.
    """
    __tablename__ = "optimization_request"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False, index=True)
    route_name = Column(String, nullable=False, index=True)
    
    # Request parameters
    depot_id = Column(Integer, ForeignKey("depot.id"), nullable=False)
    job_ids = Column(ARRAY(Integer), nullable=False)
    team_member_ids = Column(ARRAY(Integer), nullable=False)
    scheduled_date = Column(Date, nullable=False)
    optimization_goal = Column(Enum(OptimizationGoal), nullable=False, default=OptimizationGoal.MINIMUM_TIME)
    
    # Status tracking
    status = Column(Enum(OptimizationStatus), nullable=False, default=OptimizationStatus.QUEUED, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Results and errors
    error_message = Column(Text, nullable=True)
    result = Column(JSONB, nullable=True)
