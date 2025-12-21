"""
Routing client abstraction.

Provides a unified interface for different routing providers (Geoapify, GraphHopper).
"""

from typing import List, Dict, Tuple, Optional, Any, Protocol
from app.core.config import settings
from app.core.logging_config import logger
from app.services.optimization_engine.geoapify_client import GeoapifyClient
from app.services.optimization_engine.graphhopper_client import GraphHopperClient

class RoutingClient(Protocol):
    """Protocol for routing clients."""
    
    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Dict[str, List[List[float]]]:
        """Get distance and duration matrix."""
        ...

    def get_route(
        self,
        locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Optional[str]:
        """Get route polyline."""
        ...
        
    def geometry_to_coords(self, geometry: Any) -> Tuple[float, float]:
        """Convert geometry to coordinates."""
        ...


def get_routing_client() -> RoutingClient:
    """
    Factory function to get the configured routing client.
    
    Returns:
        Instance of RoutingClient implementation
    """
    provider = settings.ROUTING_PROVIDER.lower()
    
    if provider == "geoapify":
        return GeoapifyClient()
    elif provider == "graphhopper":
        return GraphHopperClient()
    else:
        logger.warning(f"Unknown routing provider '{provider}', defaulting to Geoapify")
        return GeoapifyClient()
