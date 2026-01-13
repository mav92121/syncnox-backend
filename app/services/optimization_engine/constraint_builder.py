"""
Constraint builder for OR-Tools VRP solver.

Builds constraints from model data including time windows, capacity,
working hours, breaks, and other business rules.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, time, timedelta
from ortools.constraint_solver import routing_enums_pb2, pywrapcp
from app.core.logging_config import logger
from app.services.optimization_engine.data_loader import OptimizationData
from app.models.job import PriorityLevel


class ConstraintBuilder:
    """Builds OR-Tools constraints from optimization data."""
    
    # Priority penalties (higher priority = lower penalty for not serving)
    # These must be higher than typical route costs to force assignment
    PRIORITY_PENALTIES = {
        PriorityLevel.high: 10000000,    # 10M - extremely high penalty for skipping
        PriorityLevel.medium: 5000000,   # 5M - high penalty
        PriorityLevel.low: 1000000,      # 1M - moderate penalty
    }
    
    def __init__(self, data: OptimizationData):
        """
        Initialize constraint builder.
        
        Args:
            data: Optimization data containing all entities
        """
        self.data = data
        self.scheduled_date = data.scheduled_date
    
    def add_time_windows(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager,
        time_dimension: pywrapcp.RoutingDimension
    ) -> None:
        """
        Add time window constraints for jobs.
        
        Args:
            routing: OR-Tools routing model
            manager: Routing index manager
            time_dimension: Time dimension from routing model
        """
        logger.info("Adding time window constraints")
        
        for job_idx, job in enumerate(self.data.jobs, start=1):
            node_index = manager.NodeToIndex(job_idx)
            
            if job.time_window_start and job.time_window_end:
                # Convert datetime to seconds from start of day
                start_seconds = self._datetime_to_seconds(job.time_window_start)
                end_seconds = self._datetime_to_seconds(job.time_window_end)
                
                time_dimension.CumulVar(node_index).SetRange(start_seconds, end_seconds)
                
                logger.info(
                    f"Job {job.id} (node {node_index}): time window [{start_seconds}s ({start_seconds/3600:.1f}h), "
                    f"{end_seconds}s ({end_seconds/3600:.1f}h)] = {job.time_window_start} to {job.time_window_end}"
                )
            else:
                logger.warning(f"Job {job.id} has no time window constraints")
    
    def add_working_hours(
        self,
        routing: pywrapcp.RoutingModel,
        time_dimension: pywrapcp.RoutingDimension
    ) -> None:
        """
        Add working hours constraints for team members.
        
        Args:
            routing: OR-Tools routing model
            time_dimension: Time dimension from routing model
        """
        logger.info("Adding working hours constraints")
        
        for tm_idx, team_member in enumerate(self.data.team_members):
            vehicle_id = tm_idx
            
            if team_member.work_start_time and team_member.work_end_time:
                # Convert time to seconds from midnight
                start_seconds = self._time_to_seconds(team_member.work_start_time)
                end_seconds = self._time_to_seconds(team_member.work_end_time)
                
                # Set time window for vehicle start (depot)
                start_index = routing.Start(vehicle_id)
                time_dimension.CumulVar(start_index).SetRange(start_seconds, start_seconds)
                
                # Set time window for vehicle end (depot)
                end_index = routing.End(vehicle_id)
                
                # If overtime is allowed, extend the end time
                if team_member.allowed_overtime:
                    # Allow up to 2 hours overtime
                    max_end = end_seconds + 7200
                else:
                    max_end = end_seconds
                
                time_dimension.CumulVar(end_index).SetRange(start_seconds, max_end)
                
                logger.info(
                    f"Team member {team_member.id} (vehicle {vehicle_id}): "
                    f"work hours [{start_seconds}s ({start_seconds/3600:.1f}h), {max_end}s ({max_end/3600:.1f}h)] "
                    f"= {team_member.work_start_time} to {team_member.work_end_time} "
                    f"(overtime={'yes' if team_member.allowed_overtime else 'no'})"
                )
            else:
                logger.warning(f"Team member {team_member.id} has no working hours set")
    
    def add_capacity_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager
    ) -> Optional[pywrapcp.RoutingDimension]:
        """
        Add vehicle capacity constraints.
        
        Note: Currently we don't have weight/volume data on jobs,
        so this is a placeholder for future implementation.
        
        Args:
            routing: OR-Tools routing model
            manager: Routing index manager
            
        Returns:
            Capacity dimension if created, None otherwise
        """
        logger.info("Capacity constraints: Not implemented (no job weight/volume data)")
        return None
    
    def add_break_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        time_dimension: pywrapcp.RoutingDimension
    ) -> None:
        """
        Add break time constraints for team members.
        
        Breaks are modeled as flexible intervals:
        - break_time_start/end define the WINDOW in which break can occur
        - break_duration defines the actual break length (default 30 min)
        - OR-Tools finds optimal break timing within the window
        
        Args:
            routing: OR-Tools routing model
            time_dimension: Time dimension from routing model
        """
        logger.info("Adding break constraints")
        
        for tm_idx, team_member in enumerate(self.data.team_members):
            if team_member.break_time_start and team_member.break_time_end:
                vehicle_id = tm_idx
                
                # Break window boundaries (earliest/latest times break can START)
                break_window_start = self._time_to_seconds(team_member.break_time_start)
                break_window_end = self._time_to_seconds(team_member.break_time_end)
                
                # Break duration in seconds (default 30 minutes if not set)
                break_duration_minutes = team_member.break_duration or 30
                break_duration_seconds = break_duration_minutes * 60
                
                # Adjust latest start so break can complete within window
                # e.g., if window is 12:00-14:00 and duration is 30min,
                # latest start is 13:30 so break ends by 14:00
                latest_break_start = break_window_end - break_duration_seconds
                
                # Validate: break duration must fit within the window
                if latest_break_start < break_window_start:
                    window_duration_minutes = (break_window_end - break_window_start) / 60
                    logger.error(
                        f"Team member {team_member.id}: INVALID break configuration - "
                        f"break duration ({break_duration_minutes}min) exceeds window "
                        f"({window_duration_minutes:.0f}min). "
                        f"Window: {team_member.break_time_start} to {team_member.break_time_end}. "
                        f"Skipping break constraint for this team member."
                    )
                    # Skip this team member's break - do not create an impossible interval
                    continue
                
                # Create break interval that can float within the window
                # OR-Tools will determine the optimal start time
                break_interval = routing.solver().FixedDurationIntervalVar(
                    break_window_start,    # earliest start time
                    latest_break_start,    # latest start time  
                    break_duration_seconds, # fixed duration
                    False,                 # not optional (break is mandatory)
                    f"break_tm_{team_member.id}"
                )
                
                time_dimension.SetBreakIntervalsOfVehicle(
                    [break_interval],
                    vehicle_id,
                    [0]  # No transit cost during break
                )
                
                logger.info(
                    f"Team member {team_member.id}: break window "
                    f"[{break_window_start}s ({break_window_start/3600:.1f}h), "
                    f"{break_window_end}s ({break_window_end/3600:.1f}h)] "
                    f"duration={break_duration_minutes}min"
                )
    
    def add_distance_constraints(
        self,
        routing: pywrapcp.RoutingModel,
        distance_dimension: pywrapcp.RoutingDimension
    ) -> None:
        """
        Add maximum distance constraints for team members.
        
        Args:
            routing: OR-Tools routing model
            distance_dimension: Distance dimension from routing model
        """
        logger.info("Adding distance constraints")
        
        for tm_idx, team_member in enumerate(self.data.team_members):
            if team_member.max_distance:
                vehicle_id = tm_idx
                
                # Convert km to meters
                max_distance_meters = team_member.max_distance * 1000
                
                # Set maximum distance for this vehicle
                end_index = routing.End(vehicle_id)
                distance_dimension.CumulVar(end_index).SetMax(int(max_distance_meters))
                
                logger.debug(
                    f"Team member {team_member.id}: max distance {max_distance_meters}m"
                )
    
    def set_node_penalties(
        self,
        routing: pywrapcp.RoutingModel,
        manager: pywrapcp.RoutingIndexManager
    ) -> None:
        """
        Set penalties for not serving jobs based on priority.
        
        Args:
            routing: OR-Tools routing model
            manager: Routing index manager
        """
        logger.info("Setting node penalties based on priority")
        
        for job_idx, job in enumerate(self.data.jobs, start=1):
            node_index = manager.NodeToIndex(job_idx)
            
            # Get penalty based on priority
            priority = job.priority_level or PriorityLevel.medium
            penalty = self.PRIORITY_PENALTIES.get(priority, 100000)
            
            # Allow dropping nodes with penalty
            routing.AddDisjunction([node_index], penalty)
            
            logger.debug(f"Job {job.id}: priority={priority.value}, penalty={penalty}")
    
    def _datetime_to_seconds(self, dt) -> int:
        """
        Convert datetime or time string to seconds from start of scheduled date.
        
        Args:
            dt: Can be datetime, time, or string in "HH:MM" or "HH:MM:SS" format
            
        Returns:
            Seconds from midnight
        """
        # Handle string format (e.g., "09:00" or "09:00:00")
        if isinstance(dt, str):
            parts = dt.split(":")
            hour = int(parts[0])
            minute = int(parts[1])
            second = int(parts[2]) if len(parts) > 2 else 0
            return hour * 3600 + minute * 60 + second
        
        # Handle datetime object
        if isinstance(dt, datetime):
            time_part = dt.time()
            return self._time_to_seconds(time_part)
        
        # Handle time object
        if isinstance(dt, time):
            return self._time_to_seconds(dt)
        
        raise ValueError(f"Unsupported type for time conversion: {type(dt)}")
    
    def _time_to_seconds(self, t: time) -> int:
        """Convert time to seconds from midnight."""
        return t.hour * 3600 + t.minute * 60 + t.second
    
    def get_service_times(self) -> List[int]:
        """
        Get service time for each location.
        
        Returns:
            List of service times in seconds (depot=0, then jobs)
        """
        service_times = [0]  # Depot has no service time
        
        for job in self.data.jobs:
            # Service duration is in minutes, convert to seconds
            duration_seconds = (job.service_duration or 0) * 60
            service_times.append(duration_seconds)
        
        return service_times
