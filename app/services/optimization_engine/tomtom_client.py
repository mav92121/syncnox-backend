"""
TomTom Matrix Routing v2 API client for distance and duration matrix calculation.

Supports both synchronous (≤14 locations) and asynchronous (>14 locations) matrix APIs.
Real-time traffic enabled by default.
"""

import time
import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.core.config import settings
from app.core.logging_config import logger
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


class TomTomClient:
    """Client for TomTom Matrix Routing v2 API."""
    
    BASE_URL = "https://api.tomtom.com/routing/matrix/2"
    
    # Threshold for sync vs async API (locations including depot)
    # Sync API limit is 200 cells, so sqrt(200) ≈ 14 locations for square matrix
    SYNC_LOCATION_THRESHOLD = 14
    
    # Async polling configuration
    POLL_INTERVAL_SECONDS = 2
    MAX_POLL_ATTEMPTS = 60  # 2 minutes max wait
    
    # Map internal vehicle types to TomTom travel modes
    TRAVEL_MODE_MAP = {
        "car": "car",
        "van": "car",
        "truck": "truck",
        "bike": "pedestrian",  # TomTom doesn't have bike mode
        "scooter": "car",
        "foot": "pedestrian"
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize TomTom client.
        
        Args:
            api_key: TomTom API key (defaults to env var)
        """
        self.api_key = api_key or settings.TOM_TOM_API_KEY
        if not self.api_key:
            logger.warning("TOM_TOM_API_KEY not set. Optimization will fail.")
    
    # Note: Multi-Customer feature (Sub-Customer-ID header) requires Enterprise account
    # activation with TomTom. It's not available on free tier, so we don't use it.
    
    def _build_request_payload(
        self,
        all_locations: List[Tuple[float, float]],
        vehicle_type: str
    ) -> Dict[str, Any]:
        """
        Build the request payload for TomTom Matrix API.
        
        Args:
            all_locations: List of (lon, lat) tuples
            vehicle_type: Internal vehicle type
            
        Returns:
            Request payload dict
        """
        travel_mode = self.TRAVEL_MODE_MAP.get(vehicle_type, "car")
        
        # TomTom expects {"point": {"latitude": lat, "longitude": lon}}
        origins = [
            {"point": {"latitude": lat, "longitude": lon}}
            for lon, lat in all_locations
        ]
        destinations = [
            {"point": {"latitude": lat, "longitude": lon}}
            for lon, lat in all_locations
        ]
        
        return {
            "origins": origins,
            "destinations": destinations,
            "options": {
                "departAt": "now",
                "traffic": "live",
                "routeType": "fastest",
                "travelMode": travel_mode
            }
        }
    
    def _parse_matrix_response(
        self,
        data: Dict[str, Any],
        matrix_size: int
    ) -> Dict[str, List[List[float]]]:
        """
        Parse TomTom matrix response into distances and durations matrices.
        
        Args:
            data: TomTom API response data
            matrix_size: Number of locations (for matrix dimensions)
            
        Returns:
            Dictionary with 'distances' (meters) and 'durations' (seconds) matrices
        """
        MAX_VAL = 2147483647  # Max 32-bit int, safe for OR-Tools
        
        # Initialize matrices with MAX_VAL
        distances = [[MAX_VAL] * matrix_size for _ in range(matrix_size)]
        durations = [[MAX_VAL] * matrix_size for _ in range(matrix_size)]
        
        # Parse response data
        for cell in data.get("data", []):
            origin_idx = cell.get("originIndex")
            dest_idx = cell.get("destinationIndex")
            
            if origin_idx is None or dest_idx is None:
                continue
            
            route_summary = cell.get("routeSummary")
            if route_summary:
                distances[origin_idx][dest_idx] = route_summary.get("lengthInMeters", MAX_VAL)
                durations[origin_idx][dest_idx] = route_summary.get("travelTimeInSeconds", MAX_VAL)
            # If detailedError exists, keep MAX_VAL (already set)
        
        # Force diagonals to 0
        for i in range(matrix_size):
            distances[i][i] = 0
            durations[i][i] = 0
        
        return {
            "distances": distances,
            "durations": durations
        }
    
    def _get_matrix_sync(
        self,
        all_locations: List[Tuple[float, float]],
        vehicle_type: str
    ) -> Dict[str, List[List[float]]]:
        """
        Get matrix using synchronous API (for small matrices ≤14 locations).
        
        Args:
            all_locations: List of (lon, lat) tuples
            vehicle_type: Internal vehicle type
            
        Returns:
            Dictionary with 'distances' and 'durations' matrices
        """
        payload = self._build_request_payload(all_locations, vehicle_type)
        url = f"{self.BASE_URL}?key={self.api_key}"
        
        headers = {"Content-Type": "application/json"}
        # Note: Sub-Customer-ID header requires Enterprise activation, not using it
        
        logger.info(f"TomTom sync matrix request: {len(all_locations)} locations")
        
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            data = response.json()
        
        # Check for failures
        stats = data.get("statistics", {})
        if stats.get("failures", 0) > 0:
            logger.warning(f"TomTom matrix had {stats['failures']} failed cells")
        
        return self._parse_matrix_response(data, len(all_locations))
    
    def _get_matrix_async(
        self,
        all_locations: List[Tuple[float, float]],
        vehicle_type: str
    ) -> Dict[str, List[List[float]]]:
        """
        Get matrix using asynchronous API (for large matrices >14 locations).
        
        Args:
            all_locations: List of (lon, lat) tuples
            vehicle_type: Internal vehicle type
            
        Returns:
            Dictionary with 'distances' and 'durations' matrices
        """
        payload = self._build_request_payload(all_locations, vehicle_type)
        
        headers = {"Content-Type": "application/json"}
        # Note: Sub-Customer-ID header requires Enterprise activation, not using it
        
        logger.info(f"TomTom async matrix request: {len(all_locations)} locations")
        
        with httpx.Client() as client:
            # Step 1: Submit job
            submit_url = f"{self.BASE_URL}/async?key={self.api_key}"
            response = client.post(submit_url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            submit_data = response.json()
            
            job_id = submit_data.get("jobId")
            if not job_id:
                raise Exception("TomTom async submission did not return jobId")
            
            logger.info(f"TomTom async job submitted: {job_id}")
            
            # Step 2: Poll for completion
            status_url = f"{self.BASE_URL}/async/{job_id}?key={self.api_key}"
            
            for attempt in range(self.MAX_POLL_ATTEMPTS):
                time.sleep(self.POLL_INTERVAL_SECONDS)
                
                status_response = client.get(status_url, headers=headers, timeout=30.0)
                status_response.raise_for_status()
                status_data = status_response.json()
                
                state = status_data.get("state")
                logger.debug(f"TomTom async job status: {state} (attempt {attempt + 1})")
                
                if state == "Completed":
                    break
                elif state == "Failed":
                    error = status_data.get("detailedError", {})
                    raise Exception(f"TomTom async job failed: {error.get('message', 'Unknown error')}")
            else:
                raise Exception(f"TomTom async job timed out after {self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL_SECONDS}s")
            
            # Step 3: Download result
            result_url = f"{self.BASE_URL}/async/{job_id}/result?key={self.api_key}"
            result_response = client.get(result_url, headers=headers, timeout=60.0)
            result_response.raise_for_status()
            result_data = result_response.json()
        
        # Check for failures
        stats = result_data.get("statistics", {})
        if stats.get("failures", 0) > 0:
            logger.warning(f"TomTom matrix had {stats['failures']} failed cells")
        
        return self._parse_matrix_response(result_data, len(all_locations))
    
    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Dict[str, List[List[float]]]:
        """
        Get distance and duration matrix for optimization.
        
        Automatically chooses sync or async API based on matrix size.
        
        Args:
            depot_location: (lon, lat) of depot
            job_locations: List of (lon, lat) for jobs
            vehicle_type: Internal vehicle type
            
        Returns:
            Dictionary with 'distances' (meters) and 'durations' (seconds) matrices
        """
        # Combine all locations: depot first, then jobs
        all_locations = [depot_location] + job_locations
        
        logger.info(
            f"Requesting matrix from TomTom: {len(all_locations)} locations, "
            f"vehicle_type={vehicle_type}"
        )
        
        # Log coordinates for debugging
        logger.debug(f"Coordinates (first 5): {all_locations[:5]}")
        
        try:
            # Choose sync or async based on location count
            if len(all_locations) <= self.SYNC_LOCATION_THRESHOLD:
                result = self._get_matrix_sync(all_locations, vehicle_type)
            else:
                result = self._get_matrix_async(all_locations, vehicle_type)
            
            logger.info(f"TomTom matrix computed: {len(result['distances'])}x{len(result['distances'])}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"TomTom API error {e.response.status_code}: {e.response.text}")
            raise Exception(f"Route calculation failed. TomTom API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Failed to get matrix from TomTom: {str(e)}")
            raise
    
    def get_route(
        self,
        locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Optional[str]:
        """
        Get route polyline for a sequence of locations.
        
        Note: TomTom Matrix API doesn't provide polylines.
        This is a placeholder that returns None.
        For polylines, use TomTom Routing API (separate service).
        
        Args:
            locations: List of (lon, lat) tuples in order
            vehicle_type: Internal vehicle type
            
        Returns:
            None (not implemented for matrix API)
        """
        logger.warning("TomTom Matrix client does not support get_route. Use Routing API instead.")
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
