"""
VRP Solver using Google OR-Tools.

Wraps OR-Tools routing solver with configuration for our optimization problem.
"""

from typing import Dict, List, Any, Optional
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from app.core.logging_config import logger
from app.services.optimization_engine.data_loader import OptimizationData
from app.services.optimization_engine.constraint_builder import ConstraintBuilder
from app.models.optimization_request import OptimizationGoal


class VRPSolution:
    """Container for VRP solution."""
    
    def __init__(
        self,
        routes: List[Dict[str, Any]],
        unassigned_jobs: List[int],
        total_distance: float,
        total_duration: float,
        objective_value: int,
        is_feasible: bool
    ):
        self.routes = routes
        self.unassigned_jobs = unassigned_jobs
        self.total_distance = total_distance
        self.total_duration = total_duration
        self.objective_value = objective_value
        self.is_feasible = is_feasible


class VRPSolver:
    """OR-Tools VRP solver wrapper."""
    
    def __init__(
        self,
        data: OptimizationData,
        distance_matrix: List[List[float]],
        duration_matrix: List[List[float]],
        optimization_goal: OptimizationGoal = OptimizationGoal.MINIMUM_TIME
    ):
        """
        Initialize VRP solver.
        
        Args:
            data: Optimization data
            distance_matrix: Distance matrix in meters
            duration_matrix: Duration matrix in seconds
            optimization_goal: Optimization objective
        """
        self.data = data
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        
        # Debug: Check duration matrix
        if duration_matrix:
            flat_durations = [d for row in duration_matrix for d in row if d is not None]
            avg_duration = sum(flat_durations) / len(flat_durations) if flat_durations else 0
            logger.info(f"Duration Matrix: size={len(duration_matrix)}x{len(duration_matrix)}, avg={avg_duration:.2f}s")
            
            # Log the matrix for inspection
            logger.info("Duration Matrix Content:")
            for i, row in enumerate(duration_matrix):
                logger.info(f"Row {i}: {row}")
        self.optimization_goal = optimization_goal
        self.constraint_builder = ConstraintBuilder(data)
        
        # Number of vehicles = number of team members
        self.num_vehicles = len(data.team_members)
        
        # Number of locations = depot + jobs
        self.num_locations = len(data.jobs) + 1
        
        logger.info(
            f"VRP Solver initialized: {self.num_locations} locations, "
            f"{self.num_vehicles} vehicles, goal={optimization_goal.value}"
        )
    
    def solve(self, time_limit_seconds: int = 30) -> Optional[VRPSolution]:
        """
        Solve the VRP problem.
        
        Args:
            time_limit_seconds: Time limit for solver
            
        Returns:
            VRPSolution if solution found, None otherwise
        """
        logger.info(f"Starting VRP solver (time limit: {time_limit_seconds}s)")
        
        # Create routing index manager
        manager = pywrapcp.RoutingIndexManager(
            self.num_locations,
            self.num_vehicles,
            0  # Depot index
        )
        
        # Create routing model
        routing = pywrapcp.RoutingModel(manager)
        
        # Add distance dimension
        distance_dimension = self._add_distance_dimension(routing, manager)
        
        # Add time dimension
        time_dimension = self._add_time_dimension(routing, manager)
        
        # Add constraints
        self._add_constraints(routing, manager, distance_dimension, time_dimension)
        
        # Set search parameters
        search_parameters = self._get_search_parameters(time_limit_seconds)
        
        # Solve
        logger.info("Running OR-Tools solver...")
        solution = routing.SolveWithParameters(search_parameters)
        
        if solution:
            logger.info("Solution found!")
            return self._extract_solution(routing, manager, solution)
        else:
            logger.warning("No solution found")
            return None
    
    def _add_distance_dimension(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager
    ) -> pywrapcp.RoutingDimension:
        """Add distance dimension to routing model."""
        
        def distance_callback(from_index: int, to_index: int) -> int:
            """Return distance between two nodes."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(self.distance_matrix[from_node][to_node])
        
        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        
        # Add distance dimension
        routing.AddDimension(
            transit_callback_index,
            0,  # No slack
            100000000,  # Maximum distance per vehicle (100,000 km)
            True,  # Start cumul to zero
            "Distance"
        )
        
        distance_dimension = routing.GetDimensionOrDie("Distance")
        
        # Set optimization goal if minimizing distance
        if self.optimization_goal == OptimizationGoal.MINIMUM_DISTANCE:
            distance_dimension.SetGlobalSpanCostCoefficient(100)
        
        logger.debug("Distance dimension added")
        return distance_dimension
    
    def _add_time_dimension(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager
    ) -> pywrapcp.RoutingDimension:
        """Add time dimension to routing model."""
        
        # Get service times for each location
        service_times = self.constraint_builder.get_service_times()
        
        def time_callback(from_index: int, to_index: int) -> int:
            """Return travel time + service time."""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            
            # Travel time
            travel_time = int(self.duration_matrix[from_node][to_node])
            
            # Service time at 'from' node
            service_time = service_times[from_node]
            
            return travel_time + service_time
        
        transit_callback_index = routing.RegisterTransitCallback(time_callback)
        
        # Add time dimension
        routing.AddDimension(
            transit_callback_index,
            28800,  # Allow waiting time up to 8 hours
            86400,  # Maximum time per vehicle (24 hours)
            False,  # Don't force start cumul to zero (we set it in constraints)
            "Time"
        )
        
        time_dimension = routing.GetDimensionOrDie("Time")
        
        # Set optimization goal if minimizing time
        if self.optimization_goal == OptimizationGoal.MINIMUM_TIME:
            time_dimension.SetGlobalSpanCostCoefficient(100)
        
        logger.debug("Time dimension added")
        return time_dimension
    
    def _add_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        distance_dimension: pywrapcp.RoutingDimension,
        time_dimension: pywrapcp.RoutingDimension
    ) -> None:
        """Add all constraints to routing model."""
        
        # Time window constraints
        self.constraint_builder.add_time_windows(routing, manager, time_dimension)
        
        # Working hours constraints
        self.constraint_builder.add_working_hours(routing, time_dimension)
        
        # Distance constraints
        self.constraint_builder.add_distance_constraints(routing, distance_dimension)
        
        # Priority-based penalties
        self.constraint_builder.set_node_penalties(routing, manager)
        
        # Break constraints
        self.constraint_builder.add_break_constraints(routing, time_dimension)
        
        logger.debug("All constraints added")
    
    def _get_search_parameters(
        self,
        time_limit_seconds: int
    ) -> pywrapcp.DefaultRoutingSearchParameters:
        """Get search parameters for solver."""
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        
        # ✅ Use PARALLEL_CHEAPEST_INSERTION (Better starting point than PATH_CHEAPEST_ARC)
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
        )
        
        # ✅ Optimization: Disable GLS for small instances
        # GLS is overkill for < 10 jobs and adds unnecessary overhead
        # num_locations includes depot, so < 12 means <= 10 jobs
        if self.num_locations < 12:
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.AUTOMATIC
            )
            # Hard-cap time for tiny instances (defensive)
            search_parameters.time_limit.seconds = min(5, time_limit_seconds)
        else:
            search_parameters.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_parameters.time_limit.seconds = time_limit_seconds

        search_parameters.log_search = False
        
        return search_parameters
    
    def _extract_solution(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        solution: pywrapcp.Assignment
    ) -> VRPSolution:
        """Extract solution from OR-Tools."""
        
        routes = []
        total_distance = 0
        total_duration = 0
        unassigned_jobs = []
        
        distance_dimension = routing.GetDimensionOrDie("Distance")
        time_dimension = routing.GetDimensionOrDie("Time")
        
        # Extract routes for each vehicle
        for vehicle_id in range(self.num_vehicles):
            route_distance = 0
            route_duration = 0
            route_stops = []
            route_start_distance = 0
            route_start_duration = 0
            
            # Baseline metrics (sum of individual round trips)
            route_baseline_distance = 0
            route_baseline_duration = 0
            
            index = routing.Start(vehicle_id)
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                
                # Get time at this node
                time_var = time_dimension.CumulVar(index)
                time_at_node = solution.Value(time_var)
                logger.debug(f"Node {node_index}: time={time_at_node}")
                
                # Add stop (skip depot at start)
                if node_index != 0:
                    job = self.data.jobs[node_index - 1]
                    route_stops.append({
                        "job_id": job.id,
                        "location_index": node_index,
                        "arrival_time": time_at_node
                    })
                    
                    # Add to baseline: Depot -> Job -> Depot
                    # 1. Depot -> Job
                    depot_to_job_dist = self.distance_matrix[0][node_index]
                    depot_to_job_dur = self.duration_matrix[0][node_index]
                    
                    # 2. Job -> Depot
                    job_to_depot_dist = self.distance_matrix[node_index][0]
                    job_to_depot_dur = self.duration_matrix[node_index][0]
                    
                    route_baseline_distance += (depot_to_job_dist + job_to_depot_dist)
                    route_baseline_duration += (depot_to_job_dur + job_to_depot_dur)
                
                # Move to next node
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                next_node_index = manager.IndexToNode(index)

                # Calculate metrics to next node
                dist_to_next = self.distance_matrix[node_index][next_node_index]
                dur_to_next = self.duration_matrix[node_index][next_node_index]
                
                # If current is depot (start), store as start leg
                if node_index == 0:
                    route_start_distance = dist_to_next
                    route_start_duration = dur_to_next
                else:
                    # If current is job, add to last stop
                    if route_stops:
                        route_stops[-1]["distance_to_next"] = dist_to_next
                        route_stops[-1]["duration_to_next"] = dur_to_next
                
                # Add distance and time
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id
                )
            
            # Get final distance and time
            distance_var = distance_dimension.CumulVar(routing.End(vehicle_id))
            route_distance = solution.Value(distance_var)
            
            # Get actual route duration (end time - start time)
            start_time_var = time_dimension.CumulVar(routing.Start(vehicle_id))
            end_time_var = time_dimension.CumulVar(routing.End(vehicle_id))
            start_time = solution.Value(start_time_var)
            end_time = solution.Value(end_time_var)
            route_duration = end_time - start_time  # Actual work duration
            
            # Calculate savings (clamped to 0)
            saved_distance = max(0, route_baseline_distance - route_distance)
            saved_time = max(0, route_baseline_duration - route_duration)
            
            logger.debug(
                f"Vehicle {vehicle_id}: start_time={start_time}s ({start_time/3600:.1f}h), "
                f"end_time={end_time}s ({end_time/3600:.1f}h), "
                f"duration={route_duration}s ({route_duration/3600:.1f}h)"
            )
            
            # Only add route if it has stops
            if route_stops:
                team_member = self.data.team_members[vehicle_id]
                vehicle = self.data.vehicles.get(team_member.vehicle_id)
                
                routes.append({
                    "team_member_id": team_member.id,
                    "vehicle_id": team_member.vehicle_id,
                    "vehicle_type": vehicle.type.value if vehicle else None,
                    "stops": route_stops,
                    "distance_meters": route_distance,
                    "duration_seconds": route_duration,
                    "start_distance": route_start_distance,
                    "start_duration": route_start_duration,
                    "saved_distance_meters": saved_distance,
                    "saved_time_seconds": saved_time,
                    "break_info": self._extract_break_info(
                        routing, solution, time_dimension, vehicle_id, team_member, route_stops
                    )
                })
                
                total_distance += route_distance
                total_duration += route_duration
        
        # Find unassigned jobs
        assigned_job_ids = set()
        for route in routes:
            for stop in route["stops"]:
                assigned_job_ids.add(stop["job_id"])
        
        all_job_ids = {job.id for job in self.data.jobs}
        unassigned_jobs = list(all_job_ids - assigned_job_ids)
        
        # Log why jobs were unassigned
        if unassigned_jobs:
            logger.warning(f"⚠️ Unassigned jobs: {unassigned_jobs}")
            logger.warning("Possible reasons: time windows incompatible with working hours, insufficient penalty, or unreachable locations")
        
        logger.info(
            f"Solution extracted: {len(routes)} routes, "
            f"{len(unassigned_jobs)} unassigned jobs, "
            f"total distance={total_distance}m, total time={total_duration}s"
        )
        
        return VRPSolution(
            routes=routes,
            unassigned_jobs=unassigned_jobs,
            total_distance=total_distance,
            total_duration=total_duration,
            objective_value=solution.ObjectiveValue(),
            is_feasible=True
        )
    
    def _extract_break_info(
        self,
        routing: pywrapcp.RoutingModel,
        solution: pywrapcp.Assignment,
        time_dimension: pywrapcp.RoutingDimension,
        vehicle_id: int,
        team_member,
        route_stops: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract break information from OR-Tools solution.
        
        Uses the actual break interval values from the solution object
        rather than heuristic estimation.
        
        Args:
            routing: OR-Tools routing model
            solution: OR-Tools solution assignment
            time_dimension: Time dimension from routing model
            vehicle_id: Vehicle/driver index
            team_member: The team member object
            route_stops: List of route stops with arrival times
            
        Returns:
            Dictionary with break info or None if no break configured
        """
        if not team_member.break_time_start or not team_member.break_time_end:
            return None
        
        try:
            # Get break intervals from the time dimension for this vehicle
            break_intervals = time_dimension.GetBreakIntervalsOfVehicle(vehicle_id)
            
            if not break_intervals:
                # Fallback: Calculate break from configured window since OR-Tools
                # should have scheduled the break within this window
                logger.debug(f"No break intervals from OR-Tools for vehicle {vehicle_id}, using configured break window")
                
                break_duration_minutes = team_member.break_duration or 30
                break_start_seconds = self._time_to_seconds(team_member.break_time_start)
                break_end_seconds = break_start_seconds + (break_duration_minutes * 60)
                
                return {
                    "break_start_seconds": break_start_seconds,
                    "break_end_seconds": break_end_seconds,
                    "break_duration_minutes": break_duration_minutes,
                    "break_after_stop_index": -1,
                    "break_location": {
                        "job_id": None,
                        "address_formatted": "En route",
                        "latitude": None,
                        "longitude": None
                    }
                }
            
            # Get the first (and typically only) break interval
            break_interval = break_intervals[0]
            
            # Extract actual break timing from solution
            break_start_seconds = solution.Value(break_interval.StartExpr())
            break_end_seconds = solution.Value(break_interval.EndExpr())
            break_duration_seconds = break_end_seconds - break_start_seconds
            break_duration_minutes = break_duration_seconds // 60
            
            logger.info(
                f"Vehicle {vehicle_id}: break from {break_start_seconds}s ({break_start_seconds/3600:.2f}h) "
                f"to {break_end_seconds}s ({break_end_seconds/3600:.2f}h) "
                f"(duration={break_duration_minutes}min)"
            )
            
            # Find which stop the break occurs after (based on actual break start time)
            break_after_stop_index = -1  # -1 means before first stop or during transit
            break_location = None
            break_during_transit = True  # Assume break is during transit unless proven otherwise
            
            for i, stop in enumerate(route_stops):
                arrival_time = stop["arrival_time"]
                
                # Get service duration for this job
                location_idx = stop.get("location_index", 0)
                job_for_location = None
                if location_idx > 0 and location_idx <= len(self.data.jobs):
                    job_for_location = self.data.jobs[location_idx - 1]
                    service_duration = (job_for_location.service_duration or 0) * 60
                else:
                    service_duration = 0
                
                departure_time = arrival_time + service_duration
                
                # Check if break starts exactly at or after departure from this stop
                if departure_time <= break_start_seconds:
                    break_after_stop_index = i
                    # Check if break starts at the stop location (driver waits at stop)
                    # vs during transit (driver stops en route)
                    if arrival_time <= break_start_seconds < departure_time + 60:  # Within 1 min of departure
                        break_during_transit = False
                        break_location = {
                            "job_id": stop.get("job_id"),
                            "address_formatted": job_for_location.address_formatted if job_for_location else "At stop",
                            "latitude": None,
                            "longitude": None
                        }
            
            # If break is during transit, mark location as "En route"
            if break_during_transit or break_location is None:
                break_location = {
                    "job_id": None,
                    "address_formatted": "En route",
                    "latitude": None,
                    "longitude": None
                }
            
            return {
                "break_start_seconds": break_start_seconds,
                "break_end_seconds": break_end_seconds,
                "break_duration_minutes": break_duration_minutes,
                "break_after_stop_index": break_after_stop_index,
                "break_location": break_location
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract break info for vehicle {vehicle_id}: {e}")
            # Fallback: return configured break info so it's not lost
            break_duration_minutes = team_member.break_duration or 30
            break_start_seconds = self._time_to_seconds(team_member.break_time_start)
            break_end_seconds = break_start_seconds + (break_duration_minutes * 60)
            
            return {
                "break_start_seconds": break_start_seconds,
                "break_end_seconds": break_end_seconds,
                "break_duration_minutes": break_duration_minutes,
                "break_after_stop_index": -1,
                "break_location": {
                    "job_id": None,
                    "address_formatted": "En route (estimated)",
                    "latitude": None,
                    "longitude": None
                }
            }
    
    def _time_to_seconds(self, t) -> int:
        """Convert time to seconds from midnight."""
        from datetime import time
        if isinstance(t, time):
            return t.hour * 3600 + t.minute * 60 + t.second
        return 0
