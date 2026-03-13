"""
OSRM routing client for distance/duration matrix calculation and route polylines.

Uses the self-hosted OSRM instance for the UK region.
OSRM Table API  → distance/duration matrices
OSRM Route API  → encoded polylines
"""

import time
import httpx
from typing import List, Dict, Any, Tuple, Optional

from app.core.config import settings
from app.core.logging_config import logger
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


class OSRMClient:
    """
    Client for self-hosted OSRM.

    Supports:
    - distance/duration matrix via Table API
    - route polyline via Route API
    - geometry conversion (PostGIS → coords)
    """

    MAX_INT = 2147483647  # Safe max for OR-Tools int32

    MAX_RETRIES = 3

    MAX_TABLE_SIZE = 600  # OSRM default max table size

    PROFILE = "driving"  # OSRM profile compiled into the server

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize OSRM client.

        Args:
            base_url: OSRM server base URL (defaults to settings.OSRM_BASE_URL)
        """
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.client = httpx.Client(timeout=120)

    # ---------------------------------------------------------
    # HTTP utility with retry
    # ---------------------------------------------------------

    def _retry_request(self, method: str, url: str, **kwargs):

        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt == self.MAX_RETRIES - 1:
                    raise
                sleep_time = 2 ** attempt
                logger.warning(
                    f"OSRM retry {attempt+1} sleep={sleep_time}s error={e}"
                )
                time.sleep(sleep_time)

    # ---------------------------------------------------------
    # Distance / Duration matrix (Table API)
    # ---------------------------------------------------------

    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Dict[str, List[List[float]]]:
        """
        Get distance and duration matrix via OSRM Table API.

        Args:
            depot_location: (lon, lat) of depot
            job_locations: List of (lon, lat) for jobs
            vehicle_type: Ignored — OSRM uses the compiled profile

        Returns:
            Dictionary with 'distances' (meters) and 'durations' (seconds) matrices
        """
        locations = [depot_location] + job_locations
        N = len(locations)

        logger.info(f"OSRM matrix request locations={N}")

        if N > self.MAX_TABLE_SIZE:
            raise ValueError(
                f"Too many locations ({N}). Max allowed {self.MAX_TABLE_SIZE}"
            )

        # Build coordinate string: lon,lat;lon,lat;...
        coords_str = ";".join(f"{lon},{lat}" for lon, lat in locations)

        url = f"{self.base_url}/table/v1/{self.PROFILE}/{coords_str}"

        try:
            r = self._retry_request("GET", url, params={
                "annotations": "distance,duration",
            })

            data = r.json()

            if data.get("code") != "Ok":
                raise RuntimeError(
                    f"OSRM Table error: {data.get('code')} — {data.get('message', '')}"
                )

            raw_distances = data["distances"]
            raw_durations = data["durations"]

            # Process: replace None with MAX_INT, force diagonal to 0
            distances = []
            durations = []

            for i in range(N):
                dist_row = []
                dur_row = []
                for j in range(N):
                    if i == j:
                        dist_row.append(0)
                        dur_row.append(0)
                    else:
                        d = raw_distances[i][j]
                        t = raw_durations[i][j]
                        dist_row.append(d if d is not None else self.MAX_INT)
                        dur_row.append(t if t is not None else self.MAX_INT)
                distances.append(dist_row)
                durations.append(dur_row)

            logger.info(f"OSRM matrix computed: {N}x{N}")

            return {
                "distances": distances,
                "durations": durations,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"OSRM HTTP error {e.response.status_code}: {e.response.text}")
            raise Exception(f"Matrix calculation failed: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"OSRM matrix failed: {e}")
            raise

    # ---------------------------------------------------------
    # Route polyline (Route API)
    # ---------------------------------------------------------

    def get_route(
        self,
        locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ) -> Optional[str]:
        """
        Get route polyline for a sequence of locations via OSRM Route API.

        Args:
            locations: List of (lon, lat) tuples in order
            vehicle_type: Ignored — OSRM uses the compiled profile

        Returns:
            Encoded polyline string or None if failed
        """
        if len(locations) < 2:
            logger.warning(f"Not enough locations for route: {len(locations)}")
            return None

        coords_str = ";".join(f"{lon},{lat}" for lon, lat in locations)

        url = f"{self.base_url}/route/v1/{self.PROFILE}/{coords_str}"

        try:
            r = self._retry_request("GET", url, params={
                "overview": "full",
                "geometries": "polyline",
            })

            data = r.json()

            if data.get("code") != "Ok":
                logger.warning(f"OSRM route error: {data.get('code')} — {data.get('message', '')}")
                return None

            routes = data.get("routes", [])
            if not routes:
                logger.warning("No routes in OSRM response")
                return None

            polyline = routes[0].get("geometry")

            if not polyline:
                logger.warning("No geometry in OSRM route response")
                return None

            # Log summary
            distance_m = routes[0].get("distance", 0)
            duration_s = routes[0].get("duration", 0)
            logger.info(
                f"OSRM route: {len(locations)} waypoints, "
                f"distance={distance_m/1000:.1f}km, "
                f"duration={duration_s/60:.0f}min"
            )

            return polyline

        except Exception as e:
            logger.error(f"OSRM route failed: {e}")
            return None

    # ---------------------------------------------------------
    # Geometry conversion (PostGIS → coords)
    # ---------------------------------------------------------

    def geometry_to_coords(self, geometry: Any) -> Tuple[float, float]:
        """
        Convert PostGIS geometry to (lon, lat) tuple.

        Args:
            geometry: GeoAlchemy2 WKBElement

        Returns:
            (longitude, latitude) tuple
        """
        if geometry is None:
            raise ValueError("Geometry is None")

        shape = to_shape(geometry)

        if not isinstance(shape, Point):
            raise ValueError(f"Expected Point geometry, got {type(shape)}")

        return (shape.x, shape.y)
