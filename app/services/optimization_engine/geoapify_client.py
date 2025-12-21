"""
Geoapify API client for distance/duration matrix calculation and routing.
"""

import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.logging_config import logger
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


class GeoapifyClient:
    """Client for Geoapify API."""
    
    BASE_URL = "https://api.geoapify.com/v1"
    
    # Map internal vehicle types to Geoapify profiles
    PROFILE_MAP = {
        "car": "drive",
        "van": "drive",
        "truck": "truck",
        "bike": "bicycle",
        "scooter": "bicycle",
        "foot": "walk"
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Geoapify client.
        
        Args:
            api_key: Geoapify API key (defaults to env var)
        """
        self.api_key = api_key or settings.GEOAPIFY_API_KEY
        if not self.api_key:
            logger.warning("GEOAPIFY_API_KEY not set. Optimization will fail.")
    
    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Dict[str, List[List[float]]]:
        """
        Get distance and duration matrix for optimization using Geoapify Route Matrix API.
        
        Args:
            depot_location: (lon, lat) of depot
            job_locations: List of (lon, lat) for jobs
            vehicle_type: Internal vehicle type
            
        Returns:
            Dictionary with 'distances' (meters) and 'durations' (seconds) matrices
        """
        # Combine all locations: depot first, then jobs
        all_locations = [depot_location] + job_locations
        
        # Get Geoapify profile
        profile = self.PROFILE_MAP.get(vehicle_type, "drive")
        
        logger.info(
            f"Requesting matrix from Geoapify: {len(all_locations)} locations, "
            f"profile={profile}"
        )
        
        try:
            # Prepare request payload
            # Geoapify expects dicts with 'location' key [lon, lat]
            formatted_locations = [{"location": [lon, lat]} for lon, lat in all_locations]
            
            # Log coordinates for debugging
            logger.info(f"Coordinates sent to Geoapify (first 5): {[l['location'] for l in formatted_locations[:5]]}")
            
            payload = {
                "mode": profile,
                "sources": formatted_locations,
                "targets": formatted_locations
            }
            
            url = f"{self.BASE_URL}/routematrix?apiKey={self.api_key}"
            
            with httpx.Client() as client:
                response = client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
            
            # Extract matrices
            sources_to_targets = data.get("sources_to_targets", [])
            
            if not sources_to_targets:
                raise ValueError("Empty matrix returned from Geoapify")
            
            # Max int for unreachability
            MAX_VAL = 2147483647
            
            # Initialize matrices
            n = len(all_locations)
            distances = [[MAX_VAL] * n for _ in range(n)]
            durations = [[MAX_VAL] * n for _ in range(n)]
            
            # Fill matrices from Geoapify response
            # Response is a list of lists: sources_to_targets[source_index][target_index]
            for source_idx, targets in enumerate(sources_to_targets):
                for target_data in targets:
                    target_idx = target_data.get("target_index")
                    
                    if target_idx is not None:
                        dist = target_data.get("distance", MAX_VAL)
                        time = target_data.get("time", MAX_VAL)
                        
                        distances[source_idx][target_idx] = dist
                        durations[source_idx][target_idx] = time
                        
            # Force diagonals to 0
            for i in range(n):
                distances[i][i] = 0
                durations[i][i] = 0
            
            logger.info(f"Matrix computed: {len(distances)}x{len(distances)}")
            
            return {
                "distances": distances,
                "durations": durations
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Geoapify API error: {e.response.text}")
            raise Exception(f"Route calculation failed. Please check your input and try again")
        except Exception as e:
            logger.error(f"Failed to get matrix from Geoapify: {str(e)}")
            raise

    def get_route(
        self,
        locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Optional[str]:
        """
        Get route polyline for a sequence of locations using Geoapify Routing API.
        
        Args:
            locations: List of (lon, lat) tuples in order
            vehicle_type: Internal vehicle type
            
        Returns:
            Encoded polyline string or None if failed
        """
        if len(locations) < 2:
            logger.warning(f"Not enough locations for route: {len(locations)}")
            return None
            
        profile = self.PROFILE_MAP.get(vehicle_type, "drive")
        
        try:
            # Prepare waypoints string for Geoapify
            # format: lat,lon|lat,lon|...
            waypoints = "|".join([f"{lat},{lon}" for lon, lat in locations])
            
            logger.info(f"Requesting route: {len(locations)} points, profile={profile}")
            
            params = {
                "waypoints": waypoints,
                "mode": profile,
                "apiKey": self.api_key
            }
            
            url = f"{self.BASE_URL}/routing"
            
            with httpx.Client() as client:
                response = client.get(url, params=params, timeout=30.0)
                response.raise_for_status()
                data = response.json()
            
            # Extract geometry coordinates from the first feature
            if "features" in data and data["features"]:
                feature = data["features"][0]
                geometry = feature.get("geometry", {})
                geo_type = geometry.get("type")
                coordinates = geometry.get("coordinates")
                
                if coordinates:
                    points_lat_lon = []
                    
                    if geo_type == "LineString":
                        # [[lon, lat], [lon, lat], ...]
                        points_lat_lon = [(c[1], c[0]) for c in coordinates]
                    elif geo_type == "MultiLineString":
                        # [[[lon, lat], ...], [[lon, lat], ...]]
                        for segment in coordinates:
                            points_lat_lon.extend([(c[1], c[0]) for c in segment])
                    
                    if points_lat_lon:
                        from app.utils.polyline import encode_polyline
                        encoded_polyline = encode_polyline(points_lat_lon)
                        
                        logger.info(f"Successfully fetched route (encoded length: {len(encoded_polyline)})")
                        return encoded_polyline
                
                logger.warning("No usable coordinates in routing response")
                return None
            
            logger.warning("No features in Geoapify response")
            return None
            
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Geoapify route API error {e.response.status_code}: {e.response.text}\n"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to get route from Geoapify: {str(e)}")
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
