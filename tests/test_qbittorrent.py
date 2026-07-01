import time

import pytest
import responses

from arr_exporter.collectors import qbittorrent
from tests.conftest import load_fixture

BASE = "http://qbittorrent:8080/api/v2"


@pytest.fixture(autouse=True)
def _reset_session():
    qbittorrent.reset_session()
    yield
    qbittorrent.reset_session()


@responses.activate
def test_collect_builds_points_from_maindata(settings):
    responses.add(responses.GET, f"{BASE}/sync/maindata", json=load_fixture("qbittorrent_maindata.json"))

    points = qbittorrent.collect(settings)

    measurements = [p._name for p in points]
    assert measurements == [
        "qbittorrent_transfer",
        "qbittorrent_torrents",
        "qbittorrent_torrent_detail",
        "qbittorrent_torrent_detail",
    ]


@responses.activate
def test_get_maindata_reauthenticates_on_403(settings):
    responses.add(responses.GET, f"{BASE}/sync/maindata", status=403)
    responses.add(responses.POST, f"{BASE}/auth/login", body="Ok.")
    responses.add(responses.GET, f"{BASE}/sync/maindata", json=load_fixture("qbittorrent_maindata.json"))

    maindata = qbittorrent.get_maindata(settings)

    assert maindata is not None
    assert maindata["server_state"]["connection_status"] == "connected"
    login_calls = [c for c in responses.calls if c.request.url == f"{BASE}/auth/login"]
    assert len(login_calls) == 1


@responses.activate
def test_get_maindata_fails_when_reauth_fails(settings):
    responses.add(responses.GET, f"{BASE}/sync/maindata", status=403)
    responses.add(responses.POST, f"{BASE}/auth/login", body="Fails.")

    maindata = qbittorrent.get_maindata(settings)

    assert maindata is None


@responses.activate
def test_collect_survives_maindata_failure(settings):
    responses.add(responses.GET, f"{BASE}/sync/maindata", status=500)

    points = qbittorrent.collect(settings)

    assert points == []


def test_server_state_points_line_protocol():
    maindata = load_fixture("qbittorrent_maindata.json")
    points = qbittorrent.server_state_points(maindata["server_state"])

    line = points[0].to_line_protocol()
    assert line.startswith("qbittorrent_transfer,connection_status=connected,service=qbittorrent")
    assert "dl_speed=1048576i" in line
    assert "up_speed=524288i" in line
    assert "dl_data=10737418240i" in line
    assert "up_data=5368709120i" in line
    assert "free_space_on_disk=500000000000i" in line
    assert "global_ratio=1.25" in line
    assert "dht_nodes=42i" in line


def test_torrent_summary_points_counts_by_state_group():
    maindata = load_fixture("qbittorrent_maindata.json")
    points = qbittorrent.torrent_summary_points(maindata["torrents"])

    assert len(points) == 1
    fields = points[0]._fields
    assert fields["total"] == 7
    assert fields["downloading"] == 1
    assert fields["seeding"] == 1
    assert fields["stalled_dl"] == 1
    assert fields["stalled_up"] == 1
    assert fields["paused"] == 1
    assert fields["error"] == 1
    assert fields["checking"] == 1


def test_torrent_detail_points_only_includes_problem_torrents():
    maindata = load_fixture("qbittorrent_maindata.json")
    points = qbittorrent.torrent_detail_points(maindata["torrents"])

    names = {p._tags["name"] for p in points}
    assert names == {"Old Stalled Download", "Broken Torrent"}


def test_torrent_detail_skips_recently_stalled_but_includes_unknown_age():
    torrents = {
        "recent": {
            "name": "Recently Stalled",
            "state": "stalledDL",
            "category": "movies",
            "progress": 0.5,
            "num_seeds": 1,
            "num_leechs": 1,
            "eta": 100,
            "last_activity": time.time() - 60,
        },
        "old": {
            "name": "Long Stalled",
            "state": "stalledDL",
            "category": "movies",
            "progress": 0.5,
            "num_seeds": 1,
            "num_leechs": 1,
            "eta": 100,
            "last_activity": time.time() - 700,
        },
        "unknown_age": {
            "name": "Unknown Age Stalled",
            "state": "stalledDL",
            "category": "movies",
            "progress": 0.5,
            "num_seeds": 1,
            "num_leechs": 1,
            "eta": 100,
        },
        "healthy": {
            "name": "Healthy Download",
            "state": "downloading",
            "category": "movies",
            "progress": 0.5,
            "num_seeds": 1,
            "num_leechs": 1,
            "eta": 100,
            "last_activity": time.time(),
        },
    }

    points = qbittorrent.torrent_detail_points(torrents)

    names = {p._tags["name"] for p in points}
    assert names == {"Long Stalled", "Unknown Age Stalled"}


def test_torrent_detail_points_truncates_long_names():
    torrents = {
        "hash1": {
            "name": "x" * 100,
            "state": "error",
            "category": "movies",
            "progress": 0.0,
            "num_seeds": 0,
            "num_leechs": 0,
            "eta": -1,
        },
    }

    points = qbittorrent.torrent_detail_points(torrents)

    assert len(points[0]._tags["name"]) == 64
