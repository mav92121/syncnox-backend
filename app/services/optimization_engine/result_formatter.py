"""
Result formatter for optimization solutions.

Formats the OR-Tools solution into a structured dictionary for storage.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta, time
from app.core.logging_config import logger
from app.services.optimization_engine.solver import VRPSolution
from app.services.optimization_engine.data_loader import OptimizationData


class ResultFormatter:
    """Formats VRP solution."""
    
    def __init__(self, data: OptimizationData):
        self.data = data
    
    def format(self, solution: VRPSolution) -> Dict[str, Any]:
        """
        Format solution into result dictionary.
        
        Args:
            solution: VRP solution
            
        Returns:
            Dictionary with formatted results
        """
        logger.info("Formatting optimization results")
        
        formatted_routes = []
        
        for route in solution.routes:
            team_member_id = route["team_member_id"]
            team_member = self.data.team_members[self.data.team_member_index[team_member_id]]
            
            # Calculate start time (from first stop or work start)
            # This is simplified - in real app we'd use exact times from solver
            # But solver returns seconds from midnight/start of day
            
            # Format stops
            formatted_stops = []
            for stop in route["stops"]:
                job_id = stop["job_id"]
                arrival_seconds = stop["arrival_time"]
                
                # Convert seconds to datetime
                arrival_time = self._seconds_to_datetime(arrival_seconds)
                
                formatted_stops.append({
                    "job_id": job_id,
                    "arrival_time": arrival_time.isoformat(),
                    "stop_type": "job"
                })
            
            # Fetch polyline for this route
            route_polyline = None
            try:
                # Construct ordered list of locations: Depot -> Job1 -> Job2 -> ... -> Depot
                route_locations = []
                
                # 1. Start Depot
                route_locations.append(self.data.get_location_coords(0))
                
                # 2. Jobs - look up location index from job_id
                for stop in route["stops"]:
                    job_id = stop["job_id"]
                    # Find location index for this job
                    location_idx = self.data.job_id_to_index.get(job_id)
                    if location_idx:
                        route_locations.append(self.data.get_location_coords(location_idx))
                
                # 3. End Depot
                route_locations.append(self.data.get_location_coords(0))
                
                # Get polyline from GraphHopper
                from app.services.optimization_engine.graphhopper_client import GraphHopperClient
                gh_client = GraphHopperClient()
                
                # Determine vehicle type
                vehicle_type = "car"
                if route.get("vehicle_id"):
                    vehicle = self.data.vehicles.get(route["vehicle_id"])
                    if vehicle and vehicle.type:
                        vehicle_type = vehicle.type.value
                
                route_polyline = gh_client.get_route(
                    locations=route_locations,
                    vehicle_type=vehicle_type
                )
                logger.info(f"Fetched polyline for route (team_member_id={team_member_id})")
                
            except Exception as e:
                logger.error(f"Failed to fetch polyline for route: {str(e)}")
            
            formatted_routes.append({
                "team_member_id": team_member_id,
                "team_member_name": team_member.name,
                "vehicle_id": route["vehicle_id"],
                "total_distance_meters": route["distance_meters"],
                "total_duration_seconds": route["duration_seconds"],
                "route_polyline": route_polyline,
                "stops": formatted_stops
            })
        
        result = {
            "status": "success",
            "optimization_goal": "minimum_time",  # TODO: Get from request
            "total_distance_meters": solution.total_distance,
            "total_duration_seconds": solution.total_duration,
            "routes": formatted_routes,
            "unassigned_job_ids": solution.unassigned_jobs,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Results formatted: {len(formatted_routes)} routes, "
            f"{len(solution.unassigned_jobs)} unassigned jobs"
        )
        
        return result
    
    def _seconds_to_datetime(self, seconds: int) -> datetime:
        """Convert seconds from start of day to datetime."""
        # This assumes seconds are from midnight of scheduled date
        # If seconds > 86400, it means next day
        
        base_date = self.data.scheduled_date
        # Handle both datetime and date objects
        if isinstance(base_date, datetime):
            base_date = base_date.date()
            
        # Reset to midnight
        base_date = datetime.combine(base_date, time.min)
        
        return base_date + timedelta(seconds=seconds)
