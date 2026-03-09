import pytest
import random

from app.services.optimization_engine.tomtom_client import TomTomClient


NO_OF_LOCATIONS = 99


@pytest.fixture
def tomtom_client():
    return TomTomClient()


def generate_locations(base_lon, base_lat, count):
    locations = []
    for _ in range(count):
        lon = base_lon + random.uniform(-0.05, 0.05)
        lat = base_lat + random.uniform(-0.05, 0.05)
        locations.append((lon, lat))
    return locations


def test_get_matrix_for_optimization(tomtom_client):
    depot = (74.3587, 31.5204)

    job_locations = generate_locations(74.3587, 31.5204, NO_OF_LOCATIONS)

    matrix = tomtom_client.get_matrix_for_optimization(
        depot,
        job_locations
    )

    assert matrix is not None
    assert "distances" in matrix
    assert "durations" in matrix

    # matrix should be (jobs + depot) size
    expected_size = 1 + len(job_locations)  # depot + jobs


    assert len(matrix["distances"]) == expected_size
    assert len(matrix["durations"]) == expected_size

    print("Matrix size:", len(matrix["distances"]))