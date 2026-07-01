import responses

from arr_exporter.collectors import sonarr
from tests.conftest import load_fixture

BASE = "http://sonarr:8989/api/v3"


@responses.activate
def test_collect_builds_points_from_all_endpoints(settings):
    responses.add(responses.GET, f"{BASE}/queue", json=load_fixture("sonarr_queue.json"))
    responses.add(responses.GET, f"{BASE}/series", json=load_fixture("sonarr_series.json"))
    responses.add(responses.GET, f"{BASE}/diskspace", json=load_fixture("sonarr_diskspace.json"))
    responses.add(responses.GET, f"{BASE}/calendar", json=load_fixture("sonarr_calendar.json"))

    points = sonarr.collect(settings)

    measurements = [p._name for p in points]
    assert measurements == ["sonarr_queue", "sonarr_series", "sonarr_diskspace", "sonarr_calendar"]


@responses.activate
def test_collect_survives_partial_failure(settings):
    responses.add(responses.GET, f"{BASE}/queue", status=401)
    responses.add(responses.GET, f"{BASE}/series", json=load_fixture("sonarr_series.json"))
    responses.add(responses.GET, f"{BASE}/diskspace", status=500)
    responses.add(responses.GET, f"{BASE}/calendar", json=load_fixture("sonarr_calendar.json"))

    points = sonarr.collect(settings)

    measurements = [p._name for p in points]
    assert measurements == ["sonarr_series", "sonarr_calendar"]


def test_queue_points_line_protocol():
    queue = load_fixture("sonarr_queue.json")
    points = sonarr.queue_points(queue)

    assert len(points) == 1
    line = points[0].to_line_protocol()
    assert line.startswith("sonarr_queue,service=sonarr")
    assert "total=2i" in line
    assert "status_downloading=1i" in line
    assert "status_warning=1i" in line


def test_series_points_counts_missing_episodes():
    series = load_fixture("sonarr_series.json")
    points = sonarr.series_points(series)

    line = points[0].to_line_protocol()
    assert "series_count=2i" in line
    assert "episodes_monitored=30i" in line
    assert "episodes_missing=2i" in line
