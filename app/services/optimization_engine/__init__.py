"""
Optimization package for route optimization.

Engine selection is purely flag-based via OPTIMIZATION_ENGINE in .env:
  - "nextbillion"  → NextBillion.ai Route Optimization API v2
  - "ortools"      → Google OR-Tools local VRP solver

Routing provider for polylines is separate (ROUTING_PROVIDER in .env):
  - "tomtom" | "graphhopper" | "osrm" | "geoapify"
"""

from .data_loader import OptimizationDataLoader
from .graphhopper_client import GraphHopperClient
from .nextbillion_client import NextBillionClient
from .optimization_engine import get_optimization_engine, OptimizationEngine
from .constraint_builder import ConstraintBuilder
from .solver import VRPSolver
from .result_formatter import ResultFormatter
from .route_storage import RouteStorage

__all__ = [
    "OptimizationDataLoader",
    "GraphHopperClient",
    "NextBillionClient",
    "get_optimization_engine",
    "OptimizationEngine",
    "ConstraintBuilder",
    "VRPSolver",
    "ResultFormatter",
    "RouteStorage",
]
