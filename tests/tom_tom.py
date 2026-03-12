"""
OSRM vs TomTom Accuracy Comparison Tests
=========================================
Compares the self-hosted OSRM (UK region) against TomTom's routing API
for both distance (meters) and duration (seconds) across a set of real
UK locations. Results are printed as a formatted report.

OSRM endpoint : https://routing.syncnox.com/table/v1/driving
TomTom endpoint: via TomTomClient (matrix API)

Usage:
    pytest tests/tom_tom.py -v -s
"""

import time
import httpx
import pytest
import statistics
from dataclasses import dataclass
from typing import List, Tuple, Dict

from app.services.optimization_engine.tomtom_client import TomTomClient


# ── UK test locations (lon, lat) ────────────────────────────────────────────

UK_LOCATIONS: List[Tuple[str, float, float]] = [
    # name,               lon,       lat
    ("London (Big Ben)",       -0.1246,  51.5007),
    ("Manchester (Piccadilly)",-2.2374,  53.4808),
    ("Birmingham (Bull Ring)", -1.8904,  52.4774),
    ("Leeds (City Centre)",   -1.5491,  53.8008),
    ("Bristol (Harbourside)", -2.5966,  51.4545),
    ("Liverpool (Albert Dock)",-2.9916, 53.4001),
    ("Sheffield (City Hall)", -1.4701,  53.3811),
    ("Edinburgh (Royal Mile)",-3.1883,  55.9533),
    ("Glasgow (George Sq)",   -4.2518,  55.8609),
    ("Cardiff (City Centre)", -3.1791,  51.4816),
    ("Nottingham (Old Market)",-1.1481, 52.9548),
    ("Newcastle (Quayside)",  -1.6010,  54.9695),
    ("Southampton (Docks)",   -1.4049,  50.9097),
    ("Oxford (Carfax Tower)", -1.2577,  51.7520),
    ("Cambridge (King's)",     0.1174,  52.2043),
]


OSRM_BASE_URL = "https://routing.syncnox.com"


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class PairComparison:
    origin: str
    destination: str
    tomtom_distance_m: float
    osrm_distance_m: float
    distance_diff_pct: float
    tomtom_duration_s: float
    osrm_duration_s: float
    duration_diff_pct: float


# ── OSRM client ─────────────────────────────────────────────────────────────

def osrm_table(
    locations: List[Tuple[float, float]],
    base_url: str = OSRM_BASE_URL,
) -> Dict:
    """
    Call the OSRM Table API for a list of (lon, lat) locations.
    Returns dict with 'distances' (meters) and 'durations' (seconds) matrices.
    """
    coords_str = ";".join(f"{lon},{lat}" for lon, lat in locations)
    url = f"{base_url}/table/v1/driving/{coords_str}"

    params = {
        "annotations": "distance,duration",
    }

    with httpx.Client(timeout=120) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {data.get('code')} — {data.get('message', '')}")

    return {
        "distances": data["distances"],  # meters
        "durations": data["durations"],  # seconds
    }


def osrm_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    base_url: str = OSRM_BASE_URL,
) -> Dict:
    """
    Call the OSRM Route API for a single origin-destination pair.
    Returns dict with 'distance' (meters) and 'duration' (seconds).
    """
    coords_str = f"{origin[0]},{origin[1]};{destination[0]},{destination[1]}"
    url = f"{base_url}/route/v1/driving/{coords_str}"

    params = {"overview": "false"}

    with httpx.Client(timeout=60) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    if data.get("code") != "Ok":
        raise RuntimeError(f"OSRM route error: {data.get('code')}")

    route = data["routes"][0]
    return {
        "distance": route["distance"],  # meters
        "duration": route["duration"],   # seconds
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def pct_diff(a: float, b: float) -> float:
    """Percentage difference: (a - b) / avg * 100. Returns 0 if both are 0."""
    avg = (a + b) / 2
    if avg == 0:
        return 0.0
    return ((a - b) / avg) * 100


def fmt_duration(seconds: float) -> str:
    """Format seconds to human-readable HH:MM:SS or MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def fmt_distance(meters: float) -> str:
    """Format meters to km with 1 decimal."""
    return f"{meters / 1000:.1f} km"


def print_report(
    comparisons: List[PairComparison],
    title: str = "OSRM vs TomTom Comparison"
):
    """Print a detailed report of comparisons."""
    dist_diffs = [c.distance_diff_pct for c in comparisons]
    dur_diffs = [c.duration_diff_pct for c in comparisons]

    print("\n")
    print("=" * 100)
    print(f"  {title}")
    print("=" * 100)

    # ── Summary stats ──
    print(f"\n  Total pairs compared: {len(comparisons)}")
    print(f"\n  {'Metric':<25} {'Mean Diff %':>12} {'Median %':>12} {'Std Dev':>12} {'Min %':>10} {'Max %':>10}")
    print("  " + "-" * 81)
    print(f"  {'Distance':<25} {statistics.mean(dist_diffs):>+11.2f}% {statistics.median(dist_diffs):>+11.2f}% "
          f"{statistics.stdev(dist_diffs) if len(dist_diffs) > 1 else 0:>11.2f}% "
          f"{min(dist_diffs):>+9.2f}% {max(dist_diffs):>+9.2f}%")
    print(f"  {'Duration':<25} {statistics.mean(dur_diffs):>+11.2f}% {statistics.median(dur_diffs):>+11.2f}% "
          f"{statistics.stdev(dur_diffs) if len(dur_diffs) > 1 else 0:>11.2f}% "
          f"{min(dur_diffs):>+9.2f}% {max(dur_diffs):>+9.2f}%")

    # ── Accuracy bands ──
    dist_within_5 = sum(1 for d in dist_diffs if abs(d) <= 5)
    dist_within_10 = sum(1 for d in dist_diffs if abs(d) <= 10)
    dist_within_20 = sum(1 for d in dist_diffs if abs(d) <= 20)
    dur_within_5 = sum(1 for d in dur_diffs if abs(d) <= 5)
    dur_within_10 = sum(1 for d in dur_diffs if abs(d) <= 10)
    dur_within_20 = sum(1 for d in dur_diffs if abs(d) <= 20)
    total = len(comparisons)

    print(f"\n  Accuracy Bands:")
    print(f"  {'Band':<25} {'Distance':>15} {'Duration':>15}")
    print("  " + "-" * 55)
    print(f"  {'Within ±5%':<25} {dist_within_5}/{total} ({dist_within_5/total*100:.0f}%){'':<5} {dur_within_5}/{total} ({dur_within_5/total*100:.0f}%)")
    print(f"  {'Within ±10%':<25} {dist_within_10}/{total} ({dist_within_10/total*100:.0f}%){'':<5} {dur_within_10}/{total} ({dur_within_10/total*100:.0f}%)")
    print(f"  {'Within ±20%':<25} {dist_within_20}/{total} ({dist_within_20/total*100:.0f}%){'':<5} {dur_within_20}/{total} ({dur_within_20/total*100:.0f}%)")

    # ── Per-pair detail ──
    print(f"\n  {'#':<4} {'Route':<45} {'TomTom Dist':>12} {'OSRM Dist':>12} {'Δ Dist':>10} "
          f"{'TomTom Dur':>12} {'OSRM Dur':>12} {'Δ Dur':>10}")
    print("  " + "-" * 117)

    for i, c in enumerate(comparisons, 1):
        route_label = f"{c.origin} → {c.destination}"
        if len(route_label) > 43:
            route_label = route_label[:40] + "..."
        print(
            f"  {i:<4} {route_label:<45} "
            f"{fmt_distance(c.tomtom_distance_m):>12} {fmt_distance(c.osrm_distance_m):>12} {c.distance_diff_pct:>+9.1f}% "
            f"{fmt_duration(c.tomtom_duration_s):>12} {fmt_duration(c.osrm_duration_s):>12} {c.duration_diff_pct:>+9.1f}%"
        )

    # ── Top outliers ──
    n_outliers = min(5, len(comparisons))
    by_dist = sorted(comparisons, key=lambda c: abs(c.distance_diff_pct), reverse=True)
    by_dur = sorted(comparisons, key=lambda c: abs(c.duration_diff_pct), reverse=True)

    print(f"\n  Top {n_outliers} Distance Outliers:")
    for c in by_dist[:n_outliers]:
        print(f"    {c.origin} → {c.destination}: {c.distance_diff_pct:+.1f}% "
              f"(TomTom {fmt_distance(c.tomtom_distance_m)}, OSRM {fmt_distance(c.osrm_distance_m)})")

    print(f"\n  Top {n_outliers} Duration Outliers:")
    for c in by_dur[:n_outliers]:
        print(f"    {c.origin} → {c.destination}: {c.duration_diff_pct:+.1f}% "
              f"(TomTom {fmt_duration(c.tomtom_duration_s)}, OSRM {fmt_duration(c.osrm_duration_s)})")

    print("\n" + "=" * 100)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tomtom_client():
    return TomTomClient()


@pytest.fixture
def uk_coords() -> List[Tuple[float, float]]:
    """Return just the (lon, lat) coords from our locations list."""
    return [(lon, lat) for _, lon, lat in UK_LOCATIONS]


@pytest.fixture
def uk_names() -> List[str]:
    """Return just the names from our locations list."""
    return [name for name, _, _ in UK_LOCATIONS]


# ── Test 1: Matrix comparison (ALL pairs via table/matrix API) ──────────────

MAX_INT = 2147483647


def test_matrix_accuracy_comparison(tomtom_client, uk_coords, uk_names):
    """
    Compare full NxN distance/duration matrices from OSRM Table API
    vs TomTom Matrix API for 15 real UK cities.

    This is the core accuracy test — it compares every origin→destination
    pair in a single matrix call to each service.
    """
    depot = uk_coords[0]
    jobs = uk_coords[1:]
    job_names = uk_names[1:]

    # ── Get TomTom matrix ──
    print("\n⏳ Fetching TomTom matrix...")
    t0 = time.time()
    tomtom_matrix = tomtom_client.get_matrix_for_optimization(depot, jobs)
    tomtom_time = time.time() - t0
    print(f"   TomTom done in {tomtom_time:.1f}s")

    # ── Get OSRM matrix ──
    print("⏳ Fetching OSRM matrix...")
    t0 = time.time()
    osrm_matrix = osrm_table(uk_coords)
    osrm_time = time.time() - t0
    print(f"   OSRM done in {osrm_time:.1f}s")

    all_names = uk_names  # depot + jobs (same order as uk_coords)

    # ── Build comparisons for all non-diagonal pairs ──
    comparisons: List[PairComparison] = []
    size = len(uk_coords)

    for i in range(size):
        for j in range(size):
            if i == j:
                continue

            tt_dist = tomtom_matrix["distances"][i][j]
            tt_dur = tomtom_matrix["durations"][i][j]

            # Skip pairs where TomTom returned MAX_INT (unreachable)
            if tt_dist >= MAX_INT or tt_dur >= MAX_INT:
                continue

            osrm_dist = osrm_matrix["distances"][i][j]
            osrm_dur = osrm_matrix["durations"][i][j]

            # Skip if OSRM also returned null/None
            if osrm_dist is None or osrm_dur is None:
                continue

            comparisons.append(PairComparison(
                origin=all_names[i],
                destination=all_names[j],
                tomtom_distance_m=tt_dist,
                osrm_distance_m=osrm_dist,
                distance_diff_pct=pct_diff(tt_dist, osrm_dist),
                tomtom_duration_s=tt_dur,
                osrm_duration_s=osrm_dur,
                duration_diff_pct=pct_diff(tt_dur, osrm_dur),
            ))

    assert len(comparisons) > 0, "No valid comparisons — both services returned no data"

    print_report(comparisons, title="MATRIX COMPARISON: OSRM vs TomTom (UK Cities)")

    # ── Performance comparison ──
    print(f"\n  ⏱  API Response Times:")
    print(f"     TomTom : {tomtom_time:.1f}s")
    print(f"     OSRM   : {osrm_time:.1f}s")
    print(f"     Winner : {'OSRM' if osrm_time < tomtom_time else 'TomTom'} "
          f"({abs(tomtom_time - osrm_time):.1f}s faster)\n")


# ── Test 2: Route-level comparison (point-to-point) ─────────────────────────

# Selected pairs for detailed route comparison (nearby + far)
ROUTE_PAIRS = [
    # Short routes
    (0, 13),   # London → Oxford (~90 km)
    (0, 14),   # London → Cambridge (~100 km)
    (2, 10),   # Birmingham → Nottingham (~75 km)
    (4, 9),    # Bristol → Cardiff (~70 km)
    # Medium routes
    (0, 2),    # London → Birmingham (~190 km)
    (0, 4),    # London → Bristol (~190 km)
    (3, 11),   # Leeds → Newcastle (~120 km)
    (5, 6),    # Liverpool → Sheffield (~115 km)
    # Long routes
    (0, 1),    # London → Manchester (~330 km)
    (0, 7),    # London → Edinburgh (~660 km)
    (0, 8),    # London → Glasgow (~650 km)
    (9, 7),    # Cardiff → Edinburgh (~620 km)
]


def test_route_accuracy_comparison(uk_coords, uk_names):
    """
    Compare individual route calculations (distance + duration) for
    selected UK city pairs using OSRM Route API vs TomTom Calculate Route API.

    This tests point-to-point routing accuracy, complementing the matrix test.
    """
    tomtom = TomTomClient()
    comparisons: List[PairComparison] = []

    print("\n⏳ Fetching individual routes...")

    for idx, (i, j) in enumerate(ROUTE_PAIRS):
        origin = uk_coords[i]
        dest = uk_coords[j]
        o_name = uk_names[i]
        d_name = uk_names[j]

        print(f"   [{idx+1}/{len(ROUTE_PAIRS)}] {o_name} → {d_name}")

        # ── OSRM route ──
        osrm_result = osrm_route(origin, dest)

        # ── TomTom route ──
        # Use the calculateRoute endpoint to get distance + duration
        tt_result = _tomtom_route(tomtom, origin, dest)

        if tt_result is None:
            print(f"   ⚠️  TomTom returned no route, skipping")
            continue

        comparisons.append(PairComparison(
            origin=o_name,
            destination=d_name,
            tomtom_distance_m=tt_result["distance"],
            osrm_distance_m=osrm_result["distance"],
            distance_diff_pct=pct_diff(tt_result["distance"], osrm_result["distance"]),
            tomtom_duration_s=tt_result["duration"],
            osrm_duration_s=osrm_result["duration"],
            duration_diff_pct=pct_diff(tt_result["duration"], osrm_result["duration"]),
        ))

        time.sleep(0.5)  # Rate-limit protection for TomTom

    assert len(comparisons) > 0, "No valid route comparisons"

    print_report(comparisons, title="ROUTE COMPARISON: OSRM vs TomTom (UK Selected Pairs)")


def _tomtom_route(
    client: TomTomClient,
    origin: Tuple[float, float],
    destination: Tuple[float, float],
) -> Dict | None:
    """
    Call TomTom calculateRoute for a single OD pair.
    Returns dict with 'distance' (meters) and 'duration' (seconds).
    """
    o_lon, o_lat = origin
    d_lon, d_lat = destination

    locations_str = f"{o_lat},{o_lon}:{d_lat},{d_lon}"
    url = (
        f"{client.ROUTE_URL}/{locations_str}/json"
        f"?key={client.api_key}"
        f"&travelMode=car"
        f"&traffic=true"
    )

    try:
        r = client._retry_request("GET", url)
        data = r.json()

        routes = data.get("routes", [])
        if not routes:
            return None

        summary = routes[0].get("summary", {})
        return {
            "distance": summary.get("lengthInMeters", 0),
            "duration": summary.get("travelTimeInSeconds", 0),
        }
    except Exception as e:
        print(f"   TomTom route error: {e}")
        return None


# ── Test 3: Short-distance local routes ──────────────────────────────────────

LOCAL_LOCATIONS: List[Tuple[str, float, float]] = [
    # Within London — tests local routing accuracy
    ("Buckingham Palace",   -0.1419, 51.5014),
    ("Tower of London",     -0.0761, 51.5081),
    ("British Museum",      -0.1269, 51.5194),
    ("Hyde Park Corner",    -0.1527, 51.5027),
    ("King's Cross Stn",    -0.1243, 51.5320),
    ("Canary Wharf",        -0.0197, 51.5054),
    ("Westminster Abbey",   -0.1272, 51.4993),
    ("St Paul's Cathedral", -0.0986, 51.5138),
]


def test_local_routing_accuracy(tomtom_client):
    """
    Compare OSRM vs TomTom for short-distance local routes within London.
    This tests accuracy for the kind of last-mile delivery routing
    where small differences matter most.
    """
    coords = [(lon, lat) for _, lon, lat in LOCAL_LOCATIONS]
    names = [name for name, _, _ in LOCAL_LOCATIONS]

    depot = coords[0]
    jobs = coords[1:]

    # ── TomTom matrix ──
    print("\n⏳ Fetching TomTom matrix (London local)...")
    tomtom_matrix = tomtom_client.get_matrix_for_optimization(depot, jobs)

    # ── OSRM matrix ──
    print("⏳ Fetching OSRM matrix (London local)...")
    osrm_matrix = osrm_table(coords)

    comparisons: List[PairComparison] = []
    size = len(coords)

    for i in range(size):
        for j in range(size):
            if i == j:
                continue

            tt_dist = tomtom_matrix["distances"][i][j]
            tt_dur = tomtom_matrix["durations"][i][j]

            if tt_dist >= MAX_INT or tt_dur >= MAX_INT:
                continue

            osrm_dist = osrm_matrix["distances"][i][j]
            osrm_dur = osrm_matrix["durations"][i][j]

            if osrm_dist is None or osrm_dur is None:
                continue

            comparisons.append(PairComparison(
                origin=names[i],
                destination=names[j],
                tomtom_distance_m=tt_dist,
                osrm_distance_m=osrm_dist,
                distance_diff_pct=pct_diff(tt_dist, osrm_dist),
                tomtom_duration_s=tt_dur,
                osrm_duration_s=osrm_dur,
                duration_diff_pct=pct_diff(tt_dur, osrm_dur),
            ))

    assert len(comparisons) > 0, "No valid local comparisons"

    print_report(comparisons, title="LOCAL ROUTING: OSRM vs TomTom (Within London)")