"""
NextBillion.ai Route Optimization API v2 client.

Handles:
- Building NB-format request payloads from our internal OptimizationData
- Submitting async optimization jobs
- Polling until completion
- Parsing NB responses back to our internal result format

Features leveraged:
- Multi-dimensional capacity (weight, volume, pallets)
- Skills matching (driver <-> job)
- Time windows per job
- Driver breaks (floating window)
- Priority levels
- Custom driver start/end locations
- Optimization goal (min time / min distance)
- Traffic-aware routing
- Webhook-ready (task_id returned for tracking)
"""

import time
import httpx
from datetime import datetime, time as time_type
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging_config import logger
from app.services.optimization_engine.data_loader import OptimizationData


# ---------------------------------------------------------------------------
# Profile mapping: our vehicle types -> NB routing profiles
# ---------------------------------------------------------------------------
NB_PROFILE_MAP = {
    "car": "car",
    "van": "car",
    "bus": "car",
    "small_truck": "truck",
    "truck": "truck",
    "scooter": "scooter",
    "foot": "foot",
    "bike": "bike",
    "mountain_bike": "bike",
}

# Priority mapping: our levels -> NB integer priority
NB_PRIORITY_MAP = {
    "high": 3,
    "medium": 2,
    "low": 1,
}


class NextBillionClient:
    """
    Client for NextBillion.ai Route Optimization API v2.

    Designed to be a complete drop-in replacement for the OR-Tools pipeline.
    All public methods match the expected interface in the optimization worker.
    """

    SUBMIT_URL_TEMPLATE = "{base}/optimization/v2?key={key}"
    RESULT_URL_TEMPLATE = "{base}/optimization/v2/result?id={task_id}&key={key}"

    POLL_INTERVAL = 2       # seconds between polls
    MAX_POLL_ATTEMPTS = 150 # 5 minutes max

    def __init__(self):
        self.api_key = settings.NEXTBILLION_API_KEY
        self.base_url = getattr(settings, "NEXTBILLION_BASE_URL", "https://api.nextbillion.io")

        if not self.api_key:
            raise ValueError(
                "NEXTBILLION_API_KEY is not set. "
                "Add it to your .env file or switch OPTIMIZATION_ENGINE=ortools."
            )

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _get_coords(self, data: OptimizationData, idx: int) -> Tuple[float, float]:
        """Return (lat, lon) for a location index. NB expects lat,lon."""
        lon, lat = data.get_location_coords(idx)
        return lat, lon

    # ------------------------------------------------------------------
    # Request builder
    # ------------------------------------------------------------------

    def build_request(self, data: OptimizationData) -> Dict[str, Any]:
        """
        Convert OptimizationData into a NextBillion v2 request payload.

        NB v2 format:
          locations = single object: {"id": 1, "location": ["lat,lng", ...]}
          vehicles = [{"id": tm.id, "start_index": N, "end_index": N, ...}]
          jobs = [{"id": job.id, "location_index": N, ...}]
        """
        # Build the flat 'location' array matching our location_index order
        location_strings: List[str] = []
        loc_index_map: Dict[int, int] = {}  # our location_index -> NB position

        # Cache routing client once — avoids re-instantiating per location
        from app.services.optimization_engine.routing_client import get_routing_client as _get_rc
        _rc = _get_rc()

        for our_idx in sorted(data.location_index.keys()):
            loc_obj = data.location_index[our_idx]
            # geometry_to_coords returns (longitude, latitude)
            longitude, latitude = _rc.geometry_to_coords(loc_obj.location)
            nb_pos = len(location_strings)
            location_strings.append(f"{latitude},{longitude}")  # NB expects "lat,lon"
            loc_index_map[our_idx] = nb_pos

        # NB locations is a single object (not an array)
        locations_obj = {
            "id": 1,
            "location": location_strings,
        }

        # ── Vehicles ──
        vehicles = []
        for tm_idx, tm in enumerate(data.team_members):
            vehicle = data.vehicles.get(tm.vehicle_id) if tm.vehicle_id else None
            vtype = vehicle.type.value if (vehicle and vehicle.type) else "car"
            profile = NB_PROFILE_MAP.get(vtype, "car")

            # Start location: custom start or depot (0)
            our_start_idx = data.team_member_starts.get(tm.id, 0)
            nb_start = loc_index_map[our_start_idx]
            nb_end = loc_index_map[0]  # always return to depot

            v: Dict[str, Any] = {
                "id": tm.id,
                "start_index": nb_start,
                "end_index": nb_end,
                # No 'profile' field — NB uses account-default routing profile
            }

            # Working hours time window
            if tm.work_start_time and tm.work_end_time:
                ws = self._time_to_seconds(tm.work_start_time)
                we = self._time_to_seconds(tm.work_end_time)
                if tm.allowed_overtime:
                    we += 7200  # 2h overtime
                v["time_window"] = [ws, we]

            # Max distance (km -> meters)
            if tm.max_distance:
                v["max_travel_distance"] = int(tm.max_distance * 1000)

            # Skills (array of integers via hash)
            if tm.skills:
                v["skills"] = [abs(hash(s)) % 100000 for s in tm.skills]

            # Multi-dim capacity from vehicle load_constraints
            if vehicle and vehicle.load_constraints:
                caps = self._parse_load_constraints(vehicle.load_constraints)
                if caps:
                    v["capacity"] = caps

            # Costs
            if tm.fixed_cost_for_driver is not None:
                v["fixed_cost"] = int(tm.fixed_cost_for_driver * 100)
            if tm.cost_per_km is not None:
                v["per_km_cost"] = int(tm.cost_per_km * 100)
            if tm.cost_per_hr is not None:
                v["per_hour_cost"] = int(tm.cost_per_hr * 100)

            # Breaks (floating within break_time_start..break_time_end)
            break_taken = getattr(tm, "_break_taken", False)
            if (not break_taken and
                    tm.break_time_start and
                    tm.break_time_end):
                bstart = self._time_to_seconds(tm.break_time_start)
                bend = self._time_to_seconds(tm.break_time_end)
                duration_s = (tm.break_duration or 30) * 60
                # Latest start so break fits within window
                latest_start = bend - duration_s
                if latest_start >= bstart:
                    v["breaks"] = [{
                        "time_windows": [[bstart, latest_start]],
                        "service": duration_s,
                    }]

            vehicles.append(v)

        # ── Jobs ──
        jobs = []
        any_job_has_amount = False
        for job in data.jobs:
            nb_loc_idx = loc_index_map.get(data.job_id_to_index[job.id])
            if nb_loc_idx is None:
                logger.warning(f"No NB location index for job {job.id}, skipping")
                continue

            j: Dict[str, Any] = {
                "id": job.id,
                "location_index": nb_loc_idx,
                "service": (job.service_duration or 0) * 60,  # seconds
            }

            # Time windows
            if job.time_window_start and job.time_window_end:
                tw_start = self._parse_time_value(job.time_window_start)
                tw_end = self._parse_time_value(job.time_window_end)
                if tw_start is not None and tw_end is not None and tw_start < tw_end:
                    j["time_windows"] = [[tw_start, tw_end]]

            # Priority (NB: 1=low, 2=medium, 3=high)
            if job.priority_level:
                j["priority"] = NB_PRIORITY_MAP.get(job.priority_level.value, 2)

            # Job load amounts (delivery) — if job has load_amounts, add them
            # This enables multi-dim capacity matching with vehicles.
            load_amounts = getattr(job, "load_amounts", None)
            if load_amounts:
                amounts = self._parse_load_constraints(load_amounts)
                if amounts:
                    j["delivery"] = amounts
                    any_job_has_amount = True

            # Description
            j["description"] = (
                job.address_formatted or
                f"Job {job.id}"
            )

            jobs.append(j)

        # ── Normalize capacity dimensions across all vehicles ──────────
        # NB capacity ONLY works when jobs also have delivery/pickup amounts.
        # If no jobs declare amounts, strip capacity from all vehicles to avoid
        # NB returning 0 routes silently due to unsatisfiable load constraints.
        vehicles_with_cap = [v for v in vehicles if "capacity" in v]
        if vehicles_with_cap and any_job_has_amount:
            max_dims = max(len(v["capacity"]) for v in vehicles_with_cap)
            for v in vehicles:
                if "capacity" in v:
                    while len(v["capacity"]) < max_dims:
                        v["capacity"].append(0)
                else:
                    # Unconstrained vehicles get very large capacity
                    v["capacity"] = [999999] * max_dims
        elif vehicles_with_cap and not any_job_has_amount:
            # Jobs have no load amounts — capacity would cause 0 routes. Strip it.
            logger.info(
                "Jobs have no load amounts — removing vehicle capacity from NB payload "
                "to avoid silent 0-route results. Vehicles are treated as unlimited."
            )
            for v in vehicles:
                v.pop("capacity", None)

        # ── Options ──
        options: Dict[str, Any] = {}

        # Optimization objective
        obj_value = getattr(data, "optimization_goal", None)
        if obj_value and hasattr(obj_value, "value"):
            obj_value = obj_value.value

        if obj_value == "minimum_distance":
            options["objective"] = {"travel_cost": "distance"}
        else:
            options["objective"] = {"travel_cost": "duration"}

        payload = {
            "locations": locations_obj,
            "vehicles": vehicles,
            "jobs": jobs,
            "options": options,
        }

        logger.info(
            f"NextBillion request built: {len(location_strings)} locations, "
            f"{len(vehicles)} vehicles, {len(jobs)} jobs"
        )
        return payload

    # ------------------------------------------------------------------
    # Submit & poll
    # ------------------------------------------------------------------

    def submit(self, payload: Dict[str, Any]) -> str:
        """POST optimization request to NB. Returns task_id."""
        url = self.SUBMIT_URL_TEMPLATE.format(
            base=self.base_url, key=self.api_key
        )
        logger.info(f"Submitting optimization to NextBillion: {url}")

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload)

            if resp.status_code == 403:
                body = resp.json()
                raise RuntimeError(
                    f"NextBillion API access denied (403). "
                    f"Possible causes: job locations outside your API key's geographic region, "
                    f"or account quota exceeded. Response: {body}. "
                    f"Tip: set OPTIMIZATION_ENGINE=ortools to use the local fallback solver."
                )
            if resp.status_code == 400:
                body = resp.json()
                raise RuntimeError(
                    f"NextBillion API bad request (400): "
                    f"{body.get('message', body.get('msg', body))}"
                )

            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("id") or data.get("task_id") or data.get("result", {}).get("id")
        if not task_id:
            raise RuntimeError(
                f"NextBillion did not return a task ID. Response: {data}"
            )

        logger.info(f"NextBillion task submitted: task_id={task_id}")
        return task_id

    def poll(self, task_id: str) -> Dict[str, Any]:
        """
        Poll NB result endpoint until optimization completes.
        Returns the full NB result JSON.
        Raises RuntimeError on failure or timeout.
        """
        url = self.RESULT_URL_TEMPLATE.format(
            base=self.base_url, key=self.api_key, task_id=task_id
        )

        for attempt in range(self.MAX_POLL_ATTEMPTS):
            time.sleep(self.POLL_INTERVAL)

            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    data = resp.json()
            except Exception as e:
                logger.warning(f"NB poll attempt {attempt+1} failed: {e}")
                continue

            status = (
                data.get("status") or
                data.get("result", {}).get("status") or
                ""
            ).lower()

            logger.info(f"NB poll {attempt+1}: status={status}")

            if status in ("ok", "completed", "success"):
                # NB sometimes returns "Ok" status but the result is not fully populated yet
                result_obj = data.get("result", {})
                if data.get("solution_created_time") or "routes" in result_obj or "unassigned" in result_obj:
                    return data
                else:
                    logger.info(f"NB poll {attempt+1}: Status OK, but solution is still populating. Waiting...")
                    continue
                    
            if status in ("error", "failed", "infeasible"):
                msg = (
                    data.get("message") or
                    data.get("result", {}).get("message", "Unknown error")
                )
                raise RuntimeError(f"NextBillion optimization failed: {msg}")
            # Still processing — keep polling

        raise TimeoutError(
            f"NextBillion optimization timed out after "
            f"{self.MAX_POLL_ATTEMPTS * self.POLL_INTERVAL}s for task {task_id}"
        )

    # ------------------------------------------------------------------
    # Result parser
    # ------------------------------------------------------------------

    def parse_result(
        self,
        nb_result: Dict[str, Any],
        data: OptimizationData,
    ) -> Dict[str, Any]:
        """
        Convert NextBillion response into the internal result format.

        The output shape is identical to what ResultFormatter.format() produces,
        so RouteStorage and all downstream code work without modification.
        """
        # NB wraps result under "result" key
        result_obj = nb_result.get("result", nb_result)
        routes_raw = result_obj.get("routes", [])
        unassigned_raw = result_obj.get("unassigned", [])

        # Debug: log raw NB summary
        summary = result_obj.get("summary", {})
        logger.info(
            f"NB raw result: routes={len(routes_raw)}, "
            f"unassigned={len(unassigned_raw)}, summary={summary}"
        )

        job_map = {job.id: job for job in data.jobs}
        tm_map = {tm.id: tm for tm in data.team_members}

        # Debug: log what vehicle IDs NB returned vs what we have
        nb_vehicle_ids = [r.get("vehicle") for r in routes_raw]
        logger.info(f"NB vehicle IDs in routes: {nb_vehicle_ids}")
        logger.info(f"Our team member IDs: {list(tm_map.keys())}")

        if unassigned_raw:
            for u in unassigned_raw:
                logger.warning(
                    f"NB unassigned job {u.get('id')}: {u.get('reason', 'no reason given')}"
                )

        formatted_routes = []
        total_distance = 0.0
        total_duration = 0.0

        for route in routes_raw:
            vehicle_id_nb = route.get("vehicle")  # tm.id we sent to NB
            # Always coerce to int — NB may return int or str depending on version
            try:
                vehicle_id_nb = int(vehicle_id_nb)
            except (TypeError, ValueError):
                pass
            tm = tm_map.get(vehicle_id_nb)
            if not tm:
                logger.warning(
                    f"NB route references vehicle id={vehicle_id_nb!r} "
                    f"which is not in our team_member map {list(tm_map.keys())}. "
                    f"Skipping this route."
                )
                continue

            vehicle = data.vehicles.get(tm.vehicle_id)
            vehicle_type = vehicle.type.value if (vehicle and vehicle.type) else "car"

            steps = route.get("steps", [])
            formatted_stops = []
            route_polyline = None

            # Collect ordered locations for polyline fetching
            polyline_coords: List[Tuple[float, float]] = []

            for step in steps:
                stype = step.get("type", "")
                arrival = step.get("arrival", 0)
                duration = step.get("duration", 0)  # service duration at this step

                arrival_dt = self._seconds_to_datetime(arrival, data)
                departure_dt = self._seconds_to_datetime(arrival + duration, data)

                job_id = step.get("id")  # NB returns job id for job steps
                job = job_map.get(job_id) if job_id else None

                if stype == "start":
                    loc = step.get("location", [0.0, 0.0])  # NB returns [lat, lng]
                    lat = loc[0] if isinstance(loc, list) else loc.get("lat", 0.0)
                    lon = loc[1] if isinstance(loc, list) else loc.get("lng", 0.0)
                    polyline_coords.append((lon, lat))
                    formatted_stops.append({
                        "job_id": None,
                        "arrival_time": arrival_dt.isoformat(),
                        "stop_type": "depot",
                        "latitude": lat,
                        "longitude": lon,
                        "address_formatted": data.depot.name,
                        "distance_to_next_stop_meters": step.get("distance", 0),
                        "time_to_next_stop_seconds": step.get("duration", 0),
                    })

                elif stype == "job":
                    loc = step.get("location", [0.0, 0.0])  # NB returns [lat, lng]
                    lat = loc[0] if isinstance(loc, list) else loc.get("lat", 0.0)
                    lon = loc[1] if isinstance(loc, list) else loc.get("lng", 0.0)
                    polyline_coords.append((lon, lat))
                    service_mins = (job.service_duration or 0) if job else 0
                    formatted_stops.append({
                        "job_id": job_id,
                        "arrival_time": arrival_dt.isoformat(),
                        "departure_time": departure_dt.isoformat(),
                        "stop_type": "job",
                        "latitude": lat,
                        "longitude": lon,
                        "address_formatted": (
                            job.address_formatted if job else f"Job {job_id}"
                        ),
                        "service_duration_minutes": service_mins,
                        "distance_to_next_stop_meters": step.get("distance", 0),
                        "time_to_next_stop_seconds": step.get("driving_time", 0),
                    })

                elif stype == "break":
                    # Breaks appear as steps — we'll capture them separately
                    pass

                elif stype == "end":
                    loc = step.get("location", [0.0, 0.0])  # NB returns [lat, lng]
                    lat = loc[0] if isinstance(loc, list) else loc.get("lat", 0.0)
                    lon = loc[1] if isinstance(loc, list) else loc.get("lng", 0.0)
                    polyline_coords.append((lon, lat))
                    formatted_stops.append({
                        "job_id": None,
                        "arrival_time": arrival_dt.isoformat(),
                        "stop_type": "depot",
                        "latitude": lat,
                        "longitude": lon,
                        "address_formatted": data.depot.name,
                        "distance_to_next_stop_meters": None,
                        "time_to_next_stop_seconds": None,
                    })

            # Fetch route polyline via existing routing provider (TomTom/GraphHopper)
            if len(polyline_coords) >= 2:
                try:
                    from app.services.optimization_engine.routing_client import get_routing_client
                    rc = get_routing_client()
                    route_polyline = rc.get_route(
                        locations=polyline_coords,
                        vehicle_type=vehicle_type,
                    )
                    if route_polyline:
                        logger.info(
                            f"✓ Polyline fetched for driver {tm.id} "
                            f"({len(polyline_coords)} waypoints)"
                        )
                except Exception as e:
                    logger.warning(f"Polyline fetch failed for driver {tm.id}: {e}")

            # Route summary
            route_distance = route.get("distance", 0)
            route_duration = route.get("duration", 0)
            total_distance += route_distance
            total_duration += route_duration

            # Extract break info if present
            formatted_break_info = self._extract_break_info(steps, data)

            # Idle blocks
            idle_blocks = self._calculate_idle_blocks(formatted_stops, formatted_break_info)

            formatted_routes.append({
                "team_member_id": tm.id,
                "team_member_name": tm.name,
                "vehicle_id": tm.vehicle_id,
                "total_distance_meters": route_distance,
                "total_duration_seconds": route_duration,
                "total_distance_saved_meters": 0,   # NB doesn't compute this directly
                "total_time_saved_seconds": 0,
                "route_polyline": route_polyline,
                "stops": formatted_stops,
                "break_info": formatted_break_info,
                "idle_blocks": idle_blocks,
                "eta_source": "nextbillion",
            })

        # Unassigned jobs
        unassigned_list = []
        for u in unassigned_raw:
            job_id = u.get("id")
            reason = u.get("reason", "Could not be visited within constraints")
            job = job_map.get(job_id)
            unassigned_list.append({
                "job_id": job_id,
                "reason": reason,
                "address_formatted": job.address_formatted if job else None,
            })

        return {
            "status": "success",
            "optimization_goal": "minimum_time",
            "total_distance_meters": total_distance,
            "total_duration_seconds": total_duration,
            "routes": formatted_routes,
            "unassigned_jobs": unassigned_list,
            "generated_at": datetime.utcnow().isoformat(),
            "engine": "nextbillion",
        }

    # ------------------------------------------------------------------
    # Helper: extract break info from NB steps
    # ------------------------------------------------------------------

    def _extract_break_info(
        self,
        steps: List[Dict],
        data: OptimizationData,
    ) -> Optional[Dict]:
        """Extract break info from NB step list."""
        depot_coords = data.get_location_coords(0)

        for step in steps:
            if step.get("type") == "break":
                arrival = step.get("arrival", 0)
                service = step.get("service", step.get("duration", 0))
                break_start_dt = self._seconds_to_datetime(arrival, data)
                break_end_dt = self._seconds_to_datetime(arrival + service, data)
                return {
                    "start_time": break_start_dt.isoformat(),
                    "end_time": break_end_dt.isoformat(),
                    "duration_minutes": service // 60,
                    "after_stop_index": -1,
                    "location": {
                        "job_id": None,
                        "address_formatted": "En route",
                        "latitude": depot_coords[1],
                        "longitude": depot_coords[0],
                    },
                }
        return None

    # ------------------------------------------------------------------
    # Helper: idle blocks (same logic as ResultFormatter)
    # ------------------------------------------------------------------

    def _calculate_idle_blocks(
        self,
        formatted_stops: List[Dict],
        break_info: Optional[Dict],
    ) -> List[Dict]:
        """Calculate idle time blocks between stops."""
        from datetime import timedelta

        idle_blocks = []
        break_start = break_end = None
        if break_info:
            try:
                break_start = datetime.fromisoformat(break_info["start_time"])
                break_end = datetime.fromisoformat(break_info["end_time"])
            except Exception:
                pass

        for i in range(len(formatted_stops) - 1):
            cur = formatted_stops[i]
            nxt = formatted_stops[i + 1]

            dep_str = cur.get("departure_time") or cur.get("arrival_time")
            if not dep_str:
                continue

            travel_s = cur.get("time_to_next_stop_seconds", 0) or 0
            departure = datetime.fromisoformat(dep_str)
            next_arrival = datetime.fromisoformat(nxt["arrival_time"])
            expected_arrival = departure + timedelta(seconds=travel_s)
            idle_s = (next_arrival - expected_arrival).total_seconds()

            # Subtract break overlap
            if break_start and break_end:
                overlap_start = max(departure, break_start)
                overlap_end = min(next_arrival, break_end)
                if overlap_start < overlap_end:
                    idle_s -= (overlap_end - overlap_start).total_seconds()

            idle_s = max(0, idle_s)
            if idle_s > 60:
                idle_blocks.append({
                    "start_time": expected_arrival.isoformat(),
                    "end_time": (expected_arrival + timedelta(seconds=idle_s)).isoformat(),
                    "duration_minutes": int(idle_s / 60),
                    "after_stop_index": i,
                    "location": {
                        "address_formatted": nxt.get("address_formatted", "En route"),
                        "latitude": nxt.get("latitude"),
                        "longitude": nxt.get("longitude"),
                    },
                })
        return idle_blocks

    # ------------------------------------------------------------------
    # Time / date utilities
    # ------------------------------------------------------------------

    def _time_to_seconds(self, t) -> int:
        """Convert time object or string to seconds from midnight."""
        if isinstance(t, time_type):
            return t.hour * 3600 + t.minute * 60 + t.second
        if isinstance(t, str):
            parts = t.split(":")
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) > 2 else 0
            return h * 3600 + m * 60 + s
        if isinstance(t, datetime):
            return t.hour * 3600 + t.minute * 60 + t.second
        return 0

    def _parse_time_value(self, val) -> Optional[int]:
        """Safely parse a time value to seconds, returning None on failure."""
        try:
            return self._time_to_seconds(val)
        except Exception:
            return None

    def _seconds_to_datetime(self, seconds: int, data: OptimizationData) -> datetime:
        """Convert seconds-from-midnight to a datetime on the scheduled date."""
        from datetime import timedelta, time as time_type

        base = data.scheduled_date
        if isinstance(base, datetime):
            base = base.date()
        midnight = datetime.combine(base, time_type.min)
        return midnight + timedelta(seconds=seconds)

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def _dominant_profile(self, data: OptimizationData) -> str:
        """Return the most common vehicle profile to use as default routing."""
        profiles = []
        for tm in data.team_members:
            vehicle = data.vehicles.get(tm.vehicle_id) if tm.vehicle_id else None
            vtype = vehicle.type.value if (vehicle and vehicle.type) else "car"
            profiles.append(NB_PROFILE_MAP.get(vtype, "car"))
        if profiles:
            return max(set(profiles), key=profiles.count)
        return "car"

    def _parse_load_constraints(self, load_constraints) -> Optional[List[int]]:
        """
        Parse vehicle load_constraints JSONB into a NB multi-dim capacity array.
        Expects load_constraints to be a list of dicts with 'max_value' field,
        or a list of ints.
        """
        if not load_constraints:
            return None
        try:
            if isinstance(load_constraints, list):
                caps = []
                for item in load_constraints:
                    if isinstance(item, dict):
                        caps.append(int(item.get("max_value", 0)))
                    elif isinstance(item, (int, float)):
                        caps.append(int(item))
                return caps if caps else None
        except Exception as e:
            logger.warning(f"Failed to parse load_constraints: {e}")
        return None
