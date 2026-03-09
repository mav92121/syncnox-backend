import time
import math
import httpx
import concurrent.futures
from typing import List, Tuple, Optional, Dict, Any

from app.core.config import settings
from app.core.logging_config import logger
from geoalchemy2.shape import to_shape
from shapely.geometry import Point


class TomTomClient:
    """
    Production ready TomTom routing client.

    Supports:
    - distance matrix generation
    - route calculation
    - batching
    - async job polling
    """

    BASE_URL = "https://api.tomtom.com/routing/matrix/2"
    ROUTE_URL = "https://api.tomtom.com/routing/1/calculateRoute"

    MAX_MATRIX_CELLS = 2000
    MAX_LOCATIONS_ALLOWED = 600

    SYNC_LOCATION_THRESHOLD = 14

    POLL_INTERVAL_SECONDS = 2
    MAX_POLL_ATTEMPTS = 60

    MAX_RETRIES = 3
    MAX_WORKERS = 5

    MAX_INT = 2147483647

    TRAVEL_MODE_MAP = {
        "car": "car",
        "van": "car",
        "truck": "truck",
        "bike": "pedestrian",
        "scooter": "car",
        "foot": "pedestrian",
    }

    def __init__(self, api_key: Optional[str] = None):

        self.api_key = api_key or settings.TOM_TOM_API_KEY

        if not self.api_key:
            raise ValueError("TomTom API key missing")

    # -----------------------------------------------------
    # HTTP utility with retry
    # -----------------------------------------------------

    def _retry_request(self, method: str, url: str, **kwargs):

        for attempt in range(self.MAX_RETRIES):

            try:

                with httpx.Client(timeout=60) as client:

                    response = client.request(method, url, **kwargs)

                    response.raise_for_status()

                    return response

            except Exception as e:

                if attempt == self.MAX_RETRIES - 1:
                    raise

                sleep_time = 2 ** attempt

                logger.warning(
                    f"TomTom retry {attempt+1} sleep={sleep_time}s error={e}"
                )

                time.sleep(sleep_time)

    # -----------------------------------------------------
    # Payload builder
    # -----------------------------------------------------

    def _build_payload(
        self,
        origins: List[Tuple[float, float]],
        destinations: List[Tuple[float, float]],
        vehicle_type: str
    ) -> Dict:

        travel_mode = self.TRAVEL_MODE_MAP.get(vehicle_type, "car")

        return {
            "origins": [
                {"point": {"latitude": lat, "longitude": lon}}
                for lon, lat in origins
            ],
            "destinations": [
                {"point": {"latitude": lat, "longitude": lon}}
                for lon, lat in destinations
            ],
            "options": {
                "departAt": "now",
                "traffic": "historical",
                "routeType": "fastest",
                "travelMode": travel_mode,
            },
        }

    # -----------------------------------------------------
    # Parse matrix response
    # -----------------------------------------------------

    def _parse_matrix(self, data, size):

        distances = [[self.MAX_INT] * size for _ in range(size)]
        durations = [[self.MAX_INT] * size for _ in range(size)]

        for cell in data.get("data", []):

            o = cell.get("originIndex")
            d = cell.get("destinationIndex")

            if o is None or d is None:
                continue

            summary = cell.get("routeSummary")

            if not summary:
                continue

            distances[o][d] = summary.get("lengthInMeters", self.MAX_INT)
            durations[o][d] = summary.get("travelTimeInSeconds", self.MAX_INT)

        for i in range(size):

            distances[i][i] = 0
            durations[i][i] = 0

        return {
            "distances": distances,
            "durations": durations
        }

    # -----------------------------------------------------
    # Sync matrix (small problems)
    # -----------------------------------------------------

    def _get_matrix_sync(self, locations, vehicle_type):

        payload = self._build_payload(locations, locations, vehicle_type)

        url = f"{self.BASE_URL}?key={self.api_key}"

        logger.info(f"TomTom sync matrix locations={len(locations)}")

        r = self._retry_request("POST", url, json=payload)

        data = r.json()

        return self._parse_matrix(data, len(locations))

    # -----------------------------------------------------
    # Async matrix job submission
    # -----------------------------------------------------

    def _submit_async_job(self, payload):

        url = f"{self.BASE_URL}/async?key={self.api_key}"

        r = self._retry_request("POST", url, json=payload)

        job = r.json()

        job_id = job.get("jobId")

        if not job_id:
            raise RuntimeError("TomTom jobId missing")

        return job_id

    # -----------------------------------------------------
    # Poll job
    # -----------------------------------------------------

    def _poll_job(self, job_id):

        status_url = f"{self.BASE_URL}/async/{job_id}?key={self.api_key}"

        for _ in range(self.MAX_POLL_ATTEMPTS):

            time.sleep(self.POLL_INTERVAL_SECONDS)

            r = self._retry_request("GET", status_url)

            data = r.json()

            state = data.get("state")

            if state == "Completed":
                return True

            if state == "Failed":

                logger.error(f"TomTom job failed {job_id} {data}")

                raise RuntimeError(
                    f"TomTom job failed {job_id} reason={data}"
                )

        raise TimeoutError(f"TomTom job timeout {job_id}")

    # -----------------------------------------------------
    # Download async result
    # -----------------------------------------------------

    def _download_result(self, job_id):

        url = f"{self.BASE_URL}/async/{job_id}/result?key={self.api_key}"

        r = self._retry_request("GET", url)

        return r.json()

    # -----------------------------------------------------
    # Worker thread
    # -----------------------------------------------------

    def _process_async_job(self, job):

        job_id, start_index = job

        logger.info(f"Polling TomTom job {job_id}")

        self._poll_job(job_id)

        result = self._download_result(job_id)

        return job_id, start_index, result

    # -----------------------------------------------------
    # Async matrix with batching
    # -----------------------------------------------------

    def _get_matrix_async(self, locations, vehicle_type):

        N = len(locations)

        batch_size = max(1, int(self.MAX_MATRIX_CELLS // N))

        batches = []

        for i in range(0, N, batch_size):

            origins = locations[i:i + batch_size]

            batches.append((i, origins))

        logger.info(f"TomTom async matrix locations={N} batches={len(batches)}")

        distances = [[self.MAX_INT] * N for _ in range(N)]
        durations = [[self.MAX_INT] * N for _ in range(N)]

        jobs = []

        for start_index, origins in batches:

            payload = self._build_payload(origins, locations, vehicle_type)

            job_id = self._submit_async_job(payload)

            logger.info(f"Submitted TomTom job {job_id}")

            jobs.append((job_id, start_index))

            time.sleep(1)  # rate limit protection

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.MAX_WORKERS
        ) as executor:

            futures = [
                executor.submit(self._process_async_job, job)
                for job in jobs
            ]

            for future in concurrent.futures.as_completed(futures):

                job_id, start_index, result = future.result()

                logger.info(f"TomTom job completed {job_id}")

                for cell in result.get("data", []):

                    o = cell.get("originIndex")
                    d = cell.get("destinationIndex")

                    if o is None or d is None:
                        continue

                    summary = cell.get("routeSummary")

                    if not summary:
                        continue

                    full_row = start_index + o

                    distances[full_row][d] = summary.get(
                        "lengthInMeters",
                        self.MAX_INT
                    )

                    durations[full_row][d] = summary.get(
                        "travelTimeInSeconds",
                        self.MAX_INT
                    )

        for i in range(N):

            distances[i][i] = 0
            durations[i][i] = 0

        return {
            "distances": distances,
            "durations": durations
        }

    # -----------------------------------------------------
    # Public matrix method
    # -----------------------------------------------------

    def get_matrix_for_optimization(
        self,
        depot_location: Tuple[float, float],
        job_locations: List[Tuple[float, float]],
        vehicle_type: str = "car"
    ):

        locations = [depot_location] + job_locations

        N = len(locations)

        logger.info(f"TomTom matrix request locations={N}")

        if N > self.MAX_LOCATIONS_ALLOWED:
            raise ValueError(
                f"Too many locations ({N}). Max allowed {self.MAX_LOCATIONS_ALLOWED}"
            )

        try:

            if N <= self.SYNC_LOCATION_THRESHOLD:
                return self._get_matrix_sync(locations, vehicle_type)

            return self._get_matrix_async(locations, vehicle_type)

        except httpx.HTTPStatusError as e:
            logger.error(f"TomTom HTTP error {e.response.status_code}: {e.response.text}")
            raise Exception(f"Matrix calculation failed: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"TomTom matrix failed: {e}")
            raise

    # -----------------------------------------------------
    # Route polyline calculation
    # -----------------------------------------------------

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

        travel_mode = self.TRAVEL_MODE_MAP.get(vehicle_type, "car")

        try:
            # TomTom expects lat,lon (not lon,lat)
            locations_str = ":".join(
                f"{lat},{lon}" for lon, lat in locations
            )

            url = (
                f"{self.ROUTE_URL}/{locations_str}/json"
                f"?key={self.api_key}"
                f"&travelMode={travel_mode}"
                f"&traffic=true"
                f"&routeRepresentation=encodedPolyline"
            )

            r = self._retry_request("GET", url)
            data = r.json()

            routes = data.get("routes", [])
            if not routes:
                logger.warning("No routes in TomTom response")
                return None

            route = routes[0]
            legs = route.get("legs", [])

            if not legs:
                logger.warning("No legs in TomTom route")
                return None

            # Combine polylines from all legs
            combined_points = []

            for leg in legs:
                encoded = leg.get("encodedPolyline")
                precision = leg.get("encodedPolylinePrecision", 5)

                if encoded:
                    leg_points = self._decode_polyline(encoded, precision)

                    # Avoid duplicating junction points
                    if combined_points and leg_points:
                        if combined_points[-1] == leg_points[0]:
                            leg_points = leg_points[1:]

                    combined_points.extend(leg_points)

            if not combined_points:
                logger.warning("No polyline data in TomTom response")
                return None

            encoded_polyline = self._encode_polyline(combined_points)

            logger.info(
                f"TomTom route: {len(combined_points)} points, "
                f"encoded length={len(encoded_polyline)}"
            )
            return encoded_polyline

        except Exception as e:
            logger.error(f"TomTom route failed: {e}")
            return None

    # -----------------------------------------------------
    # Polyline encoding / decoding
    # -----------------------------------------------------

    @staticmethod
    def _decode_polyline(encoded: str, precision: int = 5):

        factor = 10 ** precision
        points = []
        index = lat = lon = 0

        while index < len(encoded):
            for attr in ("lat", "lon"):
                shift = result = 0
                while True:
                    b = ord(encoded[index]) - 63
                    index += 1
                    result |= (b & 0x1F) << shift
                    shift += 5
                    if b < 0x20:
                        break
                delta = ~(result >> 1) if result & 1 else result >> 1
                if attr == "lat":
                    lat += delta
                else:
                    lon += delta

            points.append((lat / factor, lon / factor))

        return points

    @staticmethod
    def _encode_polyline(points, precision: int = 5):

        factor = 10 ** precision
        result = []
        prev_lat = prev_lon = 0

        for lat, lon in points:
            lat_int = round(lat * factor)
            lon_int = round(lon * factor)

            for delta in (lat_int - prev_lat, lon_int - prev_lon):
                value = ~(delta << 1) if delta < 0 else delta << 1
                while value >= 0x20:
                    result.append(chr((0x20 | (value & 0x1F)) + 63))
                    value >>= 5
                result.append(chr(value + 63))

            prev_lat = lat_int
            prev_lon = lon_int

        return "".join(result)

    # -----------------------------------------------------
    # Geometry conversion (PostGIS -> coords)
    # -----------------------------------------------------

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