import responses

from arr_exporter.collectors import radarr
from tests.conftest import load_fixture

BASE = "http://radarr:7878/api/v3"


@responses.activate
def test_collect_builds_points_from_all_endpoints(settings):
    responses.add(responses.GET, f"{BASE}/queue", json=load_fixture("radarr_queue.json"))
    responses.add(responses.GET, f"{BASE}/movie", json=load_fixture("radarr_movies.json"))
    responses.add(responses.GET, f"{BASE}/diskspace", json=load_fixture("radarr_diskspace.json"))
    responses.add(responses.GET, f"{BASE}/calendar", json=load_fixture("radarr_calendar.json"))

    points = radarr.collect(settings)

    measurements = [p._name for p in points]
    assert measurements == ["radarr_queue", "radarr_movies", "radarr_diskspace", "radarr_calendar"]


@responses.activate
def test_collect_survives_partial_failure(settings):
    responses.add(responses.GET, f"{BASE}/queue", json=load_fixture("radarr_queue.json"))
    responses.add(responses.GET, f"{BASE}/movie", status=401)
    responses.add(responses.GET, f"{BASE}/diskspace", json=load_fixture("radarr_diskspace.json"))
    responses.add(responses.GET, f"{BASE}/calendar", status=500)

    points = radarr.collect(settings)

    measurements = [p._name for p in points]
    assert measurements == ["radarr_queue", "radarr_diskspace"]


def test_movie_points_counts_missing():
    movies = load_fixture("radarr_movies.json")
    points = radarr.movie_points(movies)

    line = points[0].to_line_protocol()
    assert line.startswith("radarr_movies,service=radarr")
    assert "movie_count=3i" in line
    assert "monitored=2i" in line
    assert "missing=1i" in line


def test_diskspace_points_line_protocol():
    diskspace = load_fixture("radarr_diskspace.json")
    points = radarr.diskspace_points(diskspace)

    line = points[0].to_line_protocol()
    assert line.startswith("radarr_diskspace,path=/movies,service=radarr")
    assert "free_bytes=2000000000i" in line
    assert "total_bytes=8000000000i" in line
