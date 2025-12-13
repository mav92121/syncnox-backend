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
            28800,  # Allow waiting time up to 8 hours (enough to wait from start of work to late time windows)
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
        
        # Break constraints (commented out due to OR-Tools API complexity)
        # self.constraint_builder.add_break_constraints(routing, time_dimension)
        
        logger.debug("All constraints added")
    
    def _get_search_parameters(
        self,
        time_limit_seconds: int
    ) -> pywrapcp.DefaultRoutingSearchParameters:
        """Get search parameters for solver."""
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
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
                
                # Move to next node
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                
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
                    "duration_seconds": route_duration
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
