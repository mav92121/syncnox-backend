"""
Optimization engine abstraction.

Provides a unified interface for different optimization backends.
Switch engines by changing OPTIMIZATION_ENGINE in .env — no code changes required.

Supported engines:
  - "nextbillion"  → NextBillion.ai Route Optimization API v2
  - "ortools"      → Google OR-Tools local VRP solver
"""

from typing import Dict, Any, Protocol, runtime_checkable
from app.core.config import settings
from app.core.logging_config import logger
from app.services.optimization_engine.data_loader import OptimizationData


@runtime_checkable
class OptimizationEngine(Protocol):
    """
    Protocol every optimization engine must implement.

    The worker calls:
        engine = get_optimization_engine()
        result_data = engine.optimize(data)

    That's it — adding a new engine only requires:
      1. Implementing this protocol
      2. Adding it to the factory below
      3. Setting OPTIMIZATION_ENGINE=<name> in .env
    """

    def optimize(self, data: OptimizationData) -> Dict[str, Any]:
        """
        Run optimization and return result in the standard internal format.

        Args:
            data: Loaded and validated OptimizationData

        Returns:
            Dict matching ResultFormatter output shape, with at minimum:
              - routes: List[Dict]  (each with stops, team_member_id, distances, etc.)
              - unassigned_jobs: List[Dict]
              - total_distance_meters: float
              - total_duration_seconds: float
              - status: str
              - engine: str
        """
        ...


# ---------------------------------------------------------------------------
# Engine implementations
# ---------------------------------------------------------------------------

class NextBillionEngine:
    """
    NextBillion.ai Route Optimization API v2 engine.

    Wraps NextBillionClient to implement the OptimizationEngine protocol.
    """

    def optimize(self, data: OptimizationData) -> Dict[str, Any]:
        from app.services.optimization_engine.nextbillion_client import NextBillionClient

        client = NextBillionClient()
        logger.info("Running NextBillion.ai Route Optimization API")

        payload = client.build_request(data)
        task_id = client.submit(payload)
        logger.info(f"NextBillion task submitted: {task_id}")

        nb_result = client.poll(task_id)
        logger.info("NextBillion optimization completed")

        return client.parse_result(nb_result, data)


class ORToolsEngine:
    """
    Google OR-Tools local VRP solver engine.

    Wraps the existing VRPSolver + ResultFormatter pipeline.
    """

    def optimize(self, data: OptimizationData) -> Dict[str, Any]:
        from app.services.optimization_engine.routing_client import get_routing_client
        from app.services.optimization_engine.solver import VRPSolver
        from app.services.optimization_engine.result_formatter import ResultFormatter

        logger.info("Running OR-Tools VRP solver")

        routing_client = get_routing_client()
        all_coords = data.get_all_location_coords()
        depot_coords = all_coords[0]
        all_destinations = all_coords[1:]

        # Determine dominant vehicle type
        vehicle_type = "car"
        if data.team_members and data.team_members[0].vehicle_id:
            vehicle = data.vehicles.get(data.team_members[0].vehicle_id)
            if vehicle and vehicle.type:
                vehicle_type = vehicle.type.value

        matrix = routing_client.get_matrix_for_optimization(
            depot_location=depot_coords,
            job_locations=all_destinations,
            vehicle_type=vehicle_type,
        )

        num_jobs = len(data.jobs)
        if num_jobs <= 10:
            time_limit = 2
        elif num_jobs <= 40:
            time_limit = 5
        elif num_jobs <= 100:
            time_limit = 10
        else:
            time_limit = 15

        logger.info(f"Solving VRP (jobs={num_jobs}, time_limit={time_limit}s)")
        solver = VRPSolver(
            data=data,
            distance_matrix=matrix["distances"],
            duration_matrix=matrix["durations"],
            optimization_goal=data.optimization_goal,
        )
        solution = solver.solve(time_limit_seconds=time_limit)

        if not solution:
            raise RuntimeError("OR-Tools: No feasible solution found")

        formatter = ResultFormatter(data)
        return formatter.format(solution)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ENGINE_MAP = {
    "nextbillion": NextBillionEngine,
    "ortools": ORToolsEngine,
}


def get_optimization_engine() -> OptimizationEngine:
    """
    Factory: return the configured optimization engine.

    Reads OPTIMIZATION_ENGINE from settings (set via .env).
    Adding a new engine = add a class above + add it to _ENGINE_MAP.
    """
    engine_name = getattr(settings, "OPTIMIZATION_ENGINE", "ortools").lower()
    engine_cls = _ENGINE_MAP.get(engine_name)

    if engine_cls is None:
        known = ", ".join(f'"{k}"' for k in _ENGINE_MAP)
        raise ValueError(
            f"Unknown OPTIMIZATION_ENGINE='{engine_name}'. "
            f"Valid options: {known}. Check your .env file."
        )

    logger.info(f"Optimization engine: {engine_name}")
    return engine_cls()
