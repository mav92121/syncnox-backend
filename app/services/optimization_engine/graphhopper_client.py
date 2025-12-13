"""
GraphHopper API client for distance and duration matrix calculation.

Handles communication with GraphHopper Matrix API.
"""

import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.logging_config import logger
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


class GraphHopperClient:
    """Client for GraphHopper API."""
    
    BASE_URL = "https://graphhopper.com/api/1"
    
    # Map internal vehicle types to GraphHopper profiles
    PROFILE_MAP = {
        "car": "car",
        "van": "car",  # GraphHopper free tier has limited profiles
        "truck": "truck",
        "bike": "bike",
        "scooter": "scooter",
        "foot": "foot"
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize GraphHopper client.
        
        Args:
            api_key: GraphHopper API key (defaults to env var)
        """
        self.api_key = api_key or settings.GRAPHHOPPER_API_KEY
        if not self.api_key:
            logger.warning("GRAPHHOPPER_API_KEY not set. Optimization will fail.")
    
    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Dict[str, List[List[float]]]:
        """
        Get distance and duration matrix for optimization.
        
        Args:
            depot_location: (lon, lat) of depot
            job_locations: List of (lon, lat) for jobs
            vehicle_type: Internal vehicle type
            
        Returns:
            Dictionary with 'distances' (meters) and 'durations' (seconds) matrices
        """
        # Combine all locations: depot first, then jobs
        all_locations = [depot_location] + job_locations
        
        # Get GraphHopper profile
        profile = self.PROFILE_MAP.get(vehicle_type, "car")
        
        logger.info(
            f"Requesting matrix from GraphHopper: {len(all_locations)} locations, "
            f"profile={profile}"
        )
        
        try:
            # Prepare request payload
            # GraphHopper expects [lon, lat] arrays
            points = [[lon, lat] for lon, lat in all_locations]
            
            # Log coordinates for debugging
            logger.info(f"Coordinates sent to GraphHopper (first 5): {points[:5]}")
            
            payload = {
                "points": points,
                "profile": profile,
                "out_arrays": ["distances", "times"],
                "fail_fast": False
            }
            
            url = f"{self.BASE_URL}/matrix?key={self.api_key}"
            
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
            
            # Extract matrices
            # GraphHopper returns 'distances' in meters and 'times' in seconds
            # Replace None (unreachable) with a very large number
            raw_distances = data.get("distances", [])
            raw_durations = data.get("times", [])
            
            if not raw_distances or not raw_durations:
                raise ValueError("Empty matrix returned from GraphHopper")
            
            # Max int for unreachability
            MAX_VAL = 2147483647  # Max 32-bit int, safe for OR-Tools
            
            # Process matrices: handle None and force diagonal to 0
            distances = []
            for i, row in enumerate(raw_distances):
                new_row = []
                for j, val in enumerate(row):
                    if i == j:
                        new_row.append(0)  # Force diagonal to 0
                    elif val is None:
                        new_row.append(MAX_VAL)
                    else:
                        new_row.append(val)
                distances.append(new_row)
            
            durations = []
            for i, row in enumerate(raw_durations):
                new_row = []
                for j, val in enumerate(row):
                    if i == j:
                        new_row.append(0)  # Force diagonal to 0
                    elif val is None:
                        new_row.append(MAX_VAL)
                    else:
                        new_row.append(val)
                durations.append(new_row)
            
            logger.info(f"Matrix computed: {len(distances)}x{len(distances)}")
            
            return {
                "distances": distances,
                "durations": durations
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GraphHopper API error: {e.response.text}")
            raise Exception(f"GraphHopper API failed: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Failed to get matrix from GraphHopper: {str(e)}")
            raise

    def get_route(
        self,
        locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Optional[str]:
        """
        Get route polyline for a sequence of locations.
        
        Args:
            locations: List of (lon, lat) tuples in order
            vehicle_type: Internal vehicle type
            
        Returns:
            Encoded polyline string or None if failed
        """
        if len(locations) < 2:
            logger.warning(f"Not enough locations for route: {len(locations)}")
            return None
            
        profile = self.PROFILE_MAP.get(vehicle_type, "car")
        
        try:
            # Prepare request payload
            points = [[lon, lat] for lon, lat in locations]
            
            payload = {
                "points": points,
                "profile": profile,
                "elevation": False,
                "instructions": False,
                "calc_points": True,
                "points_encoded": True
            }
            
            logger.info(f"Requesting route polyline: {len(points)} points, profile={profile}")
            logger.debug(f"Route points: {points}")
            
            url = f"{self.BASE_URL}/route?key={self.api_key}"
            
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
            
            # Extract polyline from first path
            if "paths" in data and data["paths"]:
                polyline = data["paths"][0].get("points")
                if polyline:
                    logger.info(f"Successfully fetched polyline (length: {len(polyline)})")
                    return polyline
                else:
                    logger.warning("No polyline in response")
                    return None
            
            logger.warning("No paths in GraphHopper response")
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"GraphHopper route API error {e.response.status_code}: {e.response.text}\n"
                f"Request payload: {payload}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to get route from GraphHopper: {str(e)}")
            return None
    
    def geometry_to_coords(self, geometry: Any) -> Tuple[float, float]:
        """
        Convert PostGIS geometry to (lon, lat) tuple.
        
        Args:
            geometry: GeoAlchemy2 WKBElement or WKT string
            
        Returns:
            (longitude, latitude) tuple
        """
        if geometry is None:
            raise ValueError("Geometry is None")
            
        # Convert WKBElement to shapely shape
        shape = to_shape(geometry)
        
        if not isinstance(shape, Point):
            raise ValueError(f"Expected Point geometry, got {type(shape)}")
            
        return (shape.x, shape.y)
