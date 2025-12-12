"""
Route storage service.

Handles storage of optimization results into Route and RouteStop tables.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.logging_config import logger
from app.crud.route import route as route_crud
from app.crud.job import job as job_crud
from app.models.job import JobStatus
from app.services.optimization_engine.data_loader import OptimizationData


class RouteStorage:
    """Stores optimization results in database."""
    
    def __init__(self, db: Session, data: OptimizationData):
        self.db = db
        self.data = data
    
    def store_routes(
        self,
        optimization_request_id: int,
        formatted_result: Dict[str, Any],
        tenant_id: int
    ) -> List[int]:
        """
        Store routes and stops from optimization result.
        
        Args:
            optimization_request_id: ID of the optimization request
            formatted_result: Formatted result dictionary
            tenant_id: Tenant ID
            
        Returns:
            List of created route IDs
        """
        logger.info(f"Storing routes for optimization request {optimization_request_id}")
        
        routes_data = formatted_result.get("routes", [])
        if not routes_data:
            logger.warning("No routes to store")
            return []
        
        routes_to_create = []
        
        for route_data in routes_data:
            # Prepare route object
            # Polyline is already fetched in result_formatter, just use it from route_data
            route_create_data = {
                "optimization_request_id": optimization_request_id,
                "driver_id": route_data["team_member_id"],
                "vehicle_id": route_data["vehicle_id"],
                "depot_id": self.data.depot.id,
                "total_distance_meters": route_data["total_distance_meters"],
                "total_duration_seconds": route_data["total_duration_seconds"],
                "status": "planned",
                "route_polyline": route_data.get("route_polyline")  # Use polyline from formatted result
            }
            
            # Prepare stops
            stops_create_data = []
            
            # Add depot start
            stops_create_data.append({
                "stop_type": "depot_start",
                "sequence_order": 0,
                "planned_arrival_time": None,  # Start time
                "planned_departure_time": None
            })
            
            # Add job stops
            for i, stop in enumerate(route_data["stops"], start=1):
                stops_create_data.append({
                    "job_id": stop["job_id"],
                    "stop_type": "job",
                    "sequence_order": i,
                    "planned_arrival_time": datetime.fromisoformat(stop["arrival_time"]),
                    "planned_departure_time": None  # Could add service duration
                })
                
                # Update job status to assigned and set assigned_to team member
                job = job_crud.get(db=self.db, id=stop["job_id"], tenant_id=tenant_id)
                if job:
                    job.status = JobStatus.assigned
                    job.assigned_to = route_data["team_member_id"]
                    self.db.add(job)
                    self.db.commit()
                    self.db.refresh(job)
                    logger.debug(f"Job {stop['job_id']} assigned to team member {route_data['team_member_id']}")
            
            # Add depot end
            stops_create_data.append({
                "stop_type": "depot_end",
                "sequence_order": len(stops_create_data),
                "planned_arrival_time": None,
                "planned_departure_time": None
            })
            
            routes_to_create.append({
                "route": route_create_data,
                "stops": stops_create_data
            })
        
        # Bulk create routes
        created_routes = route_crud.bulk_create_routes_with_stops(
            db=self.db,
            routes_with_stops=routes_to_create,
            tenant_id=tenant_id
        )
        
        route_ids = [r.id for r in created_routes]
        logger.info(f"Created {len(route_ids)} routes: {route_ids}")
        
        return route_ids
