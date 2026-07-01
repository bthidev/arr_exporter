import logging

from influxdb_client import Point

from arr_exporter.config import Settings
from arr_exporter.http import get_json

logger = logging.getLogger(__name__)


def _api_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/v2"


def get_activity(settings: Settings) -> dict | None:
    payload = get_json(
        _api_url(settings.tautulli_url),
        params={"apikey": settings.tautulli_api_key, "cmd": "get_activity"},
    )
    if payload is None:
        return None
    return payload.get("response", {}).get("data")


def get_libraries(settings: Settings) -> list | None:
    payload = get_json(
        _api_url(settings.tautulli_url),
        params={"apikey": settings.tautulli_api_key, "cmd": "get_libraries"},
    )
    if payload is None:
        return None
    return payload.get("response", {}).get("data")


def get_history(settings: Settings, length: int = 10) -> list | None:
    payload = get_json(
        _api_url(settings.tautulli_url),
        params={"apikey": settings.tautulli_api_key, "cmd": "get_history", "length": length},
    )
    if payload is None:
        return None
    return payload.get("response", {}).get("data", {}).get("data")


def activity_points(data: dict) -> list[Point]:
    point = (
        Point("tautulli_activity")
        .tag("service", "tautulli")
        .field("stream_count", int(data.get("stream_count", 0)))
        .field("stream_count_direct_play", int(data.get("stream_count_direct_play", 0)))
        .field("stream_count_direct_stream", int(data.get("stream_count_direct_stream", 0)))
        .field("stream_count_transcode", int(data.get("stream_count_transcode", 0)))
        .field("total_bandwidth", int(data.get("total_bandwidth", 0)))
        .field("lan_bandwidth", int(data.get("lan_bandwidth", 0)))
        .field("wan_bandwidth", int(data.get("wan_bandwidth", 0)))
    )
    return [point]


def library_points(libraries: list) -> list[Point]:
    points = []
    for lib in libraries:
        point = (
            Point("tautulli_library")
            .tag("service", "tautulli")
            .tag("section_name", lib.get("section_name", "unknown"))
            .tag("section_type", lib.get("section_type", "unknown"))
            .field("count", int(lib.get("count", 0) or 0))
            .field("parent_count", int(lib.get("parent_count", 0) or 0))
            .field("child_count", int(lib.get("child_count", 0) or 0))
        )
        points.append(point)
    return points


def history_points(history: list) -> list[Point]:
    points = []
    for item in history:
        point = (
            Point("tautulli_history")
            .tag("service", "tautulli")
            .tag("user", item.get("user", "unknown"))
            .field("full_title", str(item.get("full_title", "")))
        )
        started = item.get("date")
        if started is not None:
            point.time(int(started) * 1_000_000_000)
        points.append(point)
    return points


def collect(settings: Settings) -> list[Point]:
    points: list[Point] = []

    activity = get_activity(settings)
    if activity is not None:
        points.extend(activity_points(activity))
    else:
        logger.error("Tautulli get_activity failed")

    libraries = get_libraries(settings)
    if libraries is not None:
        points.extend(library_points(libraries))
    else:
        logger.error("Tautulli get_libraries failed")

    history = get_history(settings)
    if history is not None:
        points.extend(history_points(history))
    else:
        logger.error("Tautulli get_history failed")

    return points
