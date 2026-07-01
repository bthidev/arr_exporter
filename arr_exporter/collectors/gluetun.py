import logging

import requests
from influxdb_client import Point

from arr_exporter.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

VPN_PROTOCOLS = ("openvpn", "wireguard")


def _get(url: str) -> dict | None:
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
    except requests.exceptions.RequestException:
        logger.warning("Request to %s failed", url, exc_info=True)
        return None

    if resp.status_code == 404:
        # Expected: gluetun only exposes the status endpoint for the VPN
        # protocol it is actually running.
        return None

    try:
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        logger.warning("Request to %s failed", url, exc_info=True)
        return None

    return resp.json()


def get_vpn_status(settings: Settings) -> tuple[dict, str] | None:
    base = settings.gluetun_control_url.rstrip("/")
    for protocol in VPN_PROTOCOLS:
        payload = _get(f"{base}/v1/{protocol}/status")
        if payload is not None:
            return payload, protocol
    return None


def get_public_ip(settings: Settings) -> dict | None:
    base = settings.gluetun_control_url.rstrip("/")
    return _get(f"{base}/v1/publicip/ip")


def vpn_points(
    status_payload: dict,
    protocol: str,
    ip_payload: dict | None,
    home_wan_ip: str | None,
) -> list[Point]:
    tunnel_up = 1 if status_payload.get("status") == "running" else 0

    point = Point("gluetun_vpn").tag("service", "gluetun").tag("protocol", protocol).field("tunnel_up", tunnel_up)

    public_ip = ip_payload.get("public_ip") if ip_payload else None
    if public_ip:
        point.field("public_ip", str(public_ip))
        if home_wan_ip:
            point.field("leak_detected", public_ip == home_wan_ip)

    return [point]


def collect(settings: Settings) -> list[Point]:
    points: list[Point] = []

    status_result = get_vpn_status(settings)
    if status_result is None:
        logger.error("Gluetun get_vpn_status failed")
        return points
    status_payload, protocol = status_result

    ip_payload = get_public_ip(settings)
    if ip_payload is None:
        logger.error("Gluetun get_public_ip failed")

    points.extend(vpn_points(status_payload, protocol, ip_payload, settings.home_wan_ip))

    return points
