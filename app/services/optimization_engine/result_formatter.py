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
        
        # Build job lookup map once to avoid O(n) linear search
        job_map = {job.id: job for job in self.data.jobs}
        
        formatted_routes = []
        
        for route in solution.routes:
            team_member_id = route["team_member_id"]
            team_member = self.data.team_members[self.data.team_member_index[team_member_id]]
            
            # Calculate start time (from first stop or work start)
            # This is simplified - in real app we'd use exact times from solver
            # But solver returns seconds from midnight/start of day
            
            # Format stops
            formatted_stops = []
            
            # Add starting depot stop
            # Use team member's work start time if available, otherwise use midnight
            if team_member.work_start_time:
                # Convert work_start_time to seconds and then to datetime
                depot_start_seconds = self._time_string_to_seconds(team_member.work_start_time)
                depot_arrival = self._seconds_to_datetime(depot_start_seconds)
            else:
                depot_arrival = self._seconds_to_datetime(0)  # Default to midnight
            
            depot_coords = self.data.get_location_coords(0)
            formatted_stops.append({
                "job_id": None,
                "arrival_time": depot_arrival.isoformat(),
                "stop_type": "depot",
                "latitude": depot_coords[1],  # GraphHopper returns (lon, lat)
                "longitude": depot_coords[0],
                "address_formatted": self.data.depot.name,
                "distance_to_next_stop_meters": route.get("start_distance", 0),
                "time_to_next_stop_seconds": route.get("start_duration", 0)
            })
            
            for stop in route["stops"]:
                job_id = stop["job_id"]
                arrival_seconds = stop["arrival_time"]
                
                # Convert seconds to datetime
                arrival_time = self._seconds_to_datetime(arrival_seconds)
                
                # Find the job to get location data
                job = job_map.get(job_id)
                if job:
                    # Get coordinates for this job
                    location_idx = self.data.job_id_to_index.get(job_id)
                    if location_idx:
                        coords = self.data.get_location_coords(location_idx)
                        # Calculate departure time (arrival + service duration)
                        service_duration_mins = job.service_duration or 0
                        departure_time = arrival_time + timedelta(minutes=service_duration_mins)
                        
                        formatted_stops.append({
                            "job_id": job_id,
                            "arrival_time": arrival_time.isoformat(),
                            "departure_time": departure_time.isoformat(),
                            "stop_type": "job",
                            "latitude": coords[1],  # GraphHopper returns (lon, lat)
                            "longitude": coords[0],
                            "address_formatted": job.address_formatted or "No address",
                            "service_duration_minutes": service_duration_mins,
                            "distance_to_next_stop_meters": stop.get("distance_to_next", 0),
                            "time_to_next_stop_seconds": stop.get("duration_to_next", 0)
                        })
                    else:
                        logger.warning(f"Location index not found for job {job_id}")
                else:
                    logger.warning(f"Job {job_id} not found in data")
            
            # Add ending depot stop
            # Calculate end time by adding route duration to start time
            if team_member.work_start_time:
                depot_start_seconds = self._time_string_to_seconds(team_member.work_start_time)
            else:
                depot_start_seconds = 0
            
            route_duration = route.get("duration_seconds", 0)
            depot_end_seconds = depot_start_seconds + route_duration
            depot_end_arrival = self._seconds_to_datetime(depot_end_seconds)
            
            formatted_stops.append({
                "job_id": None,
                "arrival_time": depot_end_arrival.isoformat(),
                "stop_type": "depot",
                "latitude": depot_coords[1],
                "longitude": depot_coords[0],
                "address_formatted": self.data.depot.name,
                "distance_to_next_stop_meters": None,
                "time_to_next_stop_seconds": None
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
                
                # Get polyline from Routing Provider
                from app.services.optimization_engine.routing_client import get_routing_client
                routing_client = get_routing_client()
                
                # Determine vehicle type
                vehicle_type = "car"
                if route.get("vehicle_id"):
                    vehicle = self.data.vehicles.get(route["vehicle_id"])
                    if vehicle and vehicle.type:
                        vehicle_type = vehicle.type.value
                
                route_polyline = routing_client.get_route(
                    locations=route_locations,
                    vehicle_type=vehicle_type
                )
                
                if route_polyline:
                    logger.info(f"✓ Fetched polyline for route (team_member_id={team_member_id})")
                else:
                    logger.warning(f"✗ Failed to fetch polyline for route (team_member_id={team_member_id})")
                
            except Exception as e:
                logger.error(f"Error fetching polyline for route: {str(e)}")
            
            # Process break info from solver
            break_info = route.get("break_info")
            formatted_break_info = None
            if break_info:
                formatted_break_info = self._format_break_info(break_info, depot_coords)
            
            # Calculate idle blocks (gaps between stops)
            idle_blocks = self._calculate_idle_blocks(formatted_stops)
            
            formatted_routes.append({
                "team_member_id": team_member_id,
                "team_member_name": team_member.name,
                "vehicle_id": route["vehicle_id"],
                "total_distance_meters": route["distance_meters"],
                "total_duration_seconds": route["duration_seconds"],
                "total_distance_saved_meters": route["saved_distance_meters"],
                "total_time_saved_seconds": route["saved_time_seconds"],
                "route_polyline": route_polyline,
                "stops": formatted_stops,
                "break_info": formatted_break_info,
                "idle_blocks": idle_blocks
            })
        
        result = {
            "status": "success",
            "optimization_goal": "minimum_time",  # TODO: Get from request
            "total_distance_meters": solution.total_distance,
            "total_duration_seconds": solution.total_duration,
            "routes": formatted_routes,
            "unassigned_jobs": [
                {
                    "job_id": job_id,
                    "reason": self._analyze_unassigned_reason(job_id),
                    "address_formatted": job_map.get(job_id).address_formatted if job_map.get(job_id) else None
                }
                for job_id in solution.unassigned_jobs
            ],
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
    
    def _time_string_to_seconds(self, time_input) -> int:
        """
        Convert time string or time object to seconds from midnight.
        
        Args:
            time_input: Time object or string in "HH:MM" or "HH:MM:SS" format
            
        Returns:
            Seconds from midnight
        """
        # Handle time object directly
        if isinstance(time_input, time):
            return time_input.hour * 3600 + time_input.minute * 60 + time_input.second
        
        # Handle string format
        if isinstance(time_input, str):
            parts = time_input.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return hour * 3600 + minute * 60 + second
        

        raise ValueError(f"Unsupported type for time conversion: {type(time_input)}")

    def _analyze_unassigned_reason(self, job_id: int) -> str:
        """
        Analyze why a job was unassigned.
        
        This is a heuristic analysis since the solver doesn't provide explicit reasons.
        It checks for common issues like time window incompatibility.
        
        Args:
            job_id: ID of the unassigned job
            
        Returns:
            Reason string
        """
        job = next((j for j in self.data.jobs if j.id == job_id), None)
        if not job:
            return "Job not found in optimization data"
            
        # Check 1: Time Window Feasibility
        # If job has time window, check if it overlaps with ANY team member's working hours
        if job.time_window_start and job.time_window_end:
            job_start_sec = self._time_string_to_seconds(job.time_window_start)
            job_end_sec = self._time_string_to_seconds(job.time_window_end)
            
            can_be_served_by_any = False
            
            for tm in self.data.team_members:
                if not tm.work_start_time or not tm.work_end_time:
                    # If no working hours defined, assume available 24/7 (or at least compatible)
                    can_be_served_by_any = True
                    break
                    
                tm_start_sec = self._time_string_to_seconds(tm.work_start_time)
                tm_end_sec = self._time_string_to_seconds(tm.work_end_time)
                
                # Check for overlap
                # Overlap exists if (JobStart < TmEnd) and (JobEnd > TmStart)
                if job_start_sec < tm_end_sec and job_end_sec > tm_start_sec:
                    can_be_served_by_any = True
                    break
            
            if not can_be_served_by_any:
                return "Time window is outside of all team member's working hours"

        # Check 2: Service Duration
        # If service duration is longer than any team member's shift
        service_duration_sec = (job.service_duration or 0) * 60
        if service_duration_sec > 0:
            can_fit_in_any_shift = False
            for tm in self.data.team_members:
                if not tm.work_start_time or not tm.work_end_time:
                    can_fit_in_any_shift = True 
                    break
                
                tm_start_sec = self._time_string_to_seconds(tm.work_start_time)
                tm_end_sec = self._time_string_to_seconds(tm.work_end_time)
                shift_duration = tm_end_sec - tm_start_sec
                
                if service_duration_sec <= shift_duration:
                    can_fit_in_any_shift = True
                    break
            
            if not can_fit_in_any_shift:
                return f"Service duration ({job.service_duration} min) exceeds all team member's shift lengths"

        # Check 3: Skills/Tags (Future placeholder)
        # if job.required_skills and not any(tm.has_skills(job.required_skills) for tm in self.data.team_members):
        #    return "No team member has required skills"

        # Default fallback
        return "Could not be visited within constraints"
    
    def _format_break_info(self, break_info: Dict[str, Any], depot_coords: tuple) -> Dict[str, Any]:
        """
        Format break information with proper datetime conversion.
        
        Args:
            break_info: Raw break info from solver
            depot_coords: Depot coordinates (lon, lat) for fallback location
            
        Returns:
            Formatted break info dictionary
        """
        if not break_info:
            return None
        
        # Use safe .get() access to prevent KeyError if break_info is malformed
        break_start_seconds = break_info.get("break_start_seconds")
        break_end_seconds = break_info.get("break_end_seconds")
        
        if break_start_seconds is None or break_end_seconds is None:
            logger.warning("Incomplete break_info received, skipping")
            return None
        
        break_start = self._seconds_to_datetime(break_start_seconds)
        break_end = self._seconds_to_datetime(break_end_seconds)
        
        # Get location - either the stop location or depot
        break_location = break_info.get("break_location")
        if break_location:
            # Fill in coordinates if missing
            if break_location.get("job_id"):
                location_idx = self.data.job_id_to_index.get(break_location["job_id"])
                if location_idx:
                    coords = self.data.get_location_coords(location_idx)
                    break_location["longitude"] = coords[0]
                    break_location["latitude"] = coords[1]
                else:
                    # Job not found in index - fallback to depot coords
                    logger.warning(
                        f"Break location job_id {break_location['job_id']} not found in index, "
                        f"falling back to depot coordinates"
                    )
                    break_location["longitude"] = depot_coords[0]
                    break_location["latitude"] = depot_coords[1]
            else:
                # No job_id - use depot coords
                break_location["longitude"] = depot_coords[0]
                break_location["latitude"] = depot_coords[1]
        else:
            # Break at depot (before first stop)
            break_location = {
                "job_id": None,
                "address_formatted": self.data.depot.name,
                "longitude": depot_coords[0],
                "latitude": depot_coords[1]
            }
        
        return {
            "start_time": break_start.isoformat(),
            "end_time": break_end.isoformat(),
            "duration_minutes": break_info.get("break_duration_minutes", 0),
            "after_stop_index": break_info.get("break_after_stop_index", -1),
            "location": break_location
        }
    
    def _calculate_idle_blocks(self, formatted_stops: List[Dict]) -> List[Dict[str, Any]]:
        """
        Calculate idle time blocks between stops.
        
        Idle time = gap between departure from one stop and arrival at next,
        minus travel time to next stop.
        
        Args:
            formatted_stops: List of formatted stops with arrival/departure times
            
        Returns:
            List of idle block dictionaries
        """
        idle_blocks = []
        
        for i in range(len(formatted_stops) - 1):
            current_stop = formatted_stops[i]
            next_stop = formatted_stops[i + 1]
            
            # Skip if current stop doesn't have departure_time (depot start)
            departure_time_str = current_stop.get("departure_time")
            if not departure_time_str:
                # For depot start, calculate based on arrival + 0 service time
                departure_time_str = current_stop.get("arrival_time")
            
            if not departure_time_str:
                continue
            
            # Get travel time to next stop
            travel_time_seconds = current_stop.get("time_to_next_stop_seconds", 0) or 0
            
            # Parse times
            departure_time = datetime.fromisoformat(departure_time_str)
            next_arrival_time = datetime.fromisoformat(next_stop["arrival_time"])
            
            # Calculate expected arrival at next stop (departure + travel time)
            expected_next_arrival = departure_time + timedelta(seconds=travel_time_seconds)
            
            # Idle time = actual next arrival - expected next arrival
            idle_seconds = (next_arrival_time - expected_next_arrival).total_seconds()
            
            # Only record significant idle time (> 1 minute)
            if idle_seconds > 60:
                idle_start = expected_next_arrival
                idle_end = next_arrival_time
                
                idle_blocks.append({
                    "start_time": idle_start.isoformat(),
                    "end_time": idle_end.isoformat(),
                    "duration_minutes": int(idle_seconds / 60),
                    "after_stop_index": i,
                    "location": {
                        "address_formatted": next_stop.get("address_formatted", "En route"),
                        "latitude": next_stop.get("latitude"),
                        "longitude": next_stop.get("longitude")
                    }
                })
        
        return idle_blocks

