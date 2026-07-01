import responses

from arr_exporter.collectors import tautulli
from tests.conftest import load_fixture

API_URL = "http://tautulli:8181/api/v2"


@responses.activate
def test_collect_builds_points_from_all_endpoints(settings):
    responses.add(responses.GET, API_URL, json=load_fixture("tautulli_activity.json"))
    responses.add(responses.GET, API_URL, json=load_fixture("tautulli_libraries.json"))
    responses.add(responses.GET, API_URL, json=load_fixture("tautulli_history.json"))

    points = tautulli.collect(settings)

    measurements = [p._name for p in points]
    assert "tautulli_activity" in measurements
    assert measurements.count("tautulli_library") == 2
    assert measurements.count("tautulli_history") == 2


@responses.activate
def test_collect_survives_partial_failure(settings):
    responses.add(responses.GET, API_URL, status=500)
    responses.add(responses.GET, API_URL, json=load_fixture("tautulli_libraries.json"))
    responses.add(responses.GET, API_URL, json=load_fixture("tautulli_history.json"))

    points = tautulli.collect(settings)

    measurements = [p._name for p in points]
    assert "tautulli_activity" not in measurements
    assert measurements.count("tautulli_library") == 2


def test_activity_points_line_protocol():
    data = load_fixture("tautulli_activity.json")["response"]["data"]
    points = tautulli.activity_points(data)

    assert len(points) == 1
    line = points[0].to_line_protocol()
    assert line.startswith("tautulli_activity,service=tautulli")
    assert "stream_count=2i" in line
    assert "stream_count_transcode=1i" in line
