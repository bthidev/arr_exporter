import responses

from arr_exporter.collectors import gluetun
from tests.conftest import load_fixture

BASE = "http://gluetun:8000/v1"


@responses.activate
def test_collect_builds_points_from_wireguard(settings):
    responses.add(responses.GET, f"{BASE}/wireguard/status", json=load_fixture("gluetun_wireguard_status.json"))
    responses.add(responses.GET, f"{BASE}/publicip/ip", json=load_fixture("gluetun_publicip.json"))

    points = gluetun.collect(settings)

    assert len(points) == 1
    point = points[0]
    assert point._name == "gluetun_vpn"
    assert point._tags["protocol"] == "wireguard"
    assert point._fields["tunnel_up"] == 1
    assert point._fields["public_ip"] == "203.0.113.42"
    assert "leak_detected" not in point._fields


@responses.activate
def test_collect_falls_back_to_openvpn(settings):
    responses.add(responses.GET, f"{BASE}/wireguard/status", status=404)
    responses.add(responses.GET, f"{BASE}/openvpn/status", json=load_fixture("gluetun_openvpn_status.json"))
    responses.add(responses.GET, f"{BASE}/publicip/ip", json=load_fixture("gluetun_publicip.json"))

    points = gluetun.collect(settings)

    assert points[0]._tags["protocol"] == "openvpn"


@responses.activate
def test_collect_reports_tunnel_down(settings):
    responses.add(responses.GET, f"{BASE}/wireguard/status", json={"status": "stopped"})
    responses.add(responses.GET, f"{BASE}/publicip/ip", json=load_fixture("gluetun_publicip.json"))

    points = gluetun.collect(settings)

    assert points[0]._fields["tunnel_up"] == 0


@responses.activate
def test_collect_detects_leak_when_home_wan_ip_matches(settings):
    settings.home_wan_ip = "203.0.113.42"
    responses.add(responses.GET, f"{BASE}/wireguard/status", json=load_fixture("gluetun_wireguard_status.json"))
    responses.add(responses.GET, f"{BASE}/publicip/ip", json=load_fixture("gluetun_publicip.json"))

    points = gluetun.collect(settings)

    assert points[0]._fields["leak_detected"] is True


@responses.activate
def test_collect_no_leak_when_home_wan_ip_differs(settings):
    settings.home_wan_ip = "198.51.100.1"
    responses.add(responses.GET, f"{BASE}/wireguard/status", json=load_fixture("gluetun_wireguard_status.json"))
    responses.add(responses.GET, f"{BASE}/publicip/ip", json=load_fixture("gluetun_publicip.json"))

    points = gluetun.collect(settings)

    assert points[0]._fields["leak_detected"] is False


@responses.activate
def test_collect_survives_publicip_failure(settings):
    responses.add(responses.GET, f"{BASE}/wireguard/status", json=load_fixture("gluetun_wireguard_status.json"))
    responses.add(responses.GET, f"{BASE}/publicip/ip", status=500)

    points = gluetun.collect(settings)

    assert len(points) == 1
    assert points[0]._fields["tunnel_up"] == 1
    assert "public_ip" not in points[0]._fields


@responses.activate
def test_collect_returns_empty_when_no_protocol_available(settings):
    responses.add(responses.GET, f"{BASE}/wireguard/status", status=404)
    responses.add(responses.GET, f"{BASE}/openvpn/status", status=404)

    points = gluetun.collect(settings)

    assert points == []
