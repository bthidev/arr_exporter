import logging
from datetime import datetime, timedelta, timezone

from influxdb_client import Point

from arr_exporter.config import Settings
from arr_exporter.http import get_json

logger = logging.getLogger(__name__)

CALENDAR_DAYS_AHEAD = 7


def _get(settings: Settings, path: str, params: dict | None = None) -> dict | list | None:
    url = f"{settings.sonarr_url.rstrip('/')}/api/v3/{path}"
    headers = {"X-Api-Key": settings.sonarr_api_key}
    return get_json(url, params=params, headers=headers)


def get_queue(settings: Settings) -> dict | None:
    return _get(settings, "queue", params={"pageSize": 250})


def get_series(settings: Settings) -> list | None:
    return _get(settings, "series")


def get_diskspace(settings: Settings) -> list | None:
    return _get(settings, "diskspace")


def get_calendar(settings: Settings) -> list | None:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=CALENDAR_DAYS_AHEAD)
    return _get(
        settings,
        "calendar",
        params={"start": now.date().isoformat(), "end": end.date().isoformat()},
    )


def queue_points(queue: dict) -> list[Point]:
    records = queue.get("records", [])
    status_counts: dict[str, int] = {}
    for record in records:
        status = record.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    point = Point("sonarr_queue").tag("service", "sonarr").field("total", len(records))
    for status, count in status_counts.items():
        point.field(f"status_{status}", count)
    return [point]


def series_points(series: list) -> list[Point]:
    episodes_total = 0
    episodes_missing = 0
    for show in series:
        stats = show.get("statistics", {})
        episodes_total += int(stats.get("episodeCount", 0) or 0)
        episodes_missing += int(stats.get("episodeCount", 0) or 0) - int(
            stats.get("episodeFileCount", 0) or 0
        )

    point = (
        Point("sonarr_series")
        .tag("service", "sonarr")
        .field("series_count", len(series))
        .field("episodes_monitored", episodes_total)
        .field("episodes_missing", max(episodes_missing, 0))
    )
    return [point]


def diskspace_points(diskspace: list) -> list[Point]:
    points = []
    for disk in diskspace:
        point = (
            Point("sonarr_diskspace")
            .tag("service", "sonarr")
            .tag("path", disk.get("path", "unknown"))
            .field("free_bytes", int(disk.get("freeSpace", 0) or 0))
            .field("total_bytes", int(disk.get("totalSpace", 0) or 0))
        )
        points.append(point)
    return points


def calendar_points(calendar: list) -> list[Point]:
    point = Point("sonarr_calendar").tag("service", "sonarr").field("upcoming_count", len(calendar))
    return [point]


def collect(settings: Settings) -> list[Point]:
    points: list[Point] = []

    queue = get_queue(settings)
    if queue is not None:
        points.extend(queue_points(queue))
    else:
        logger.error("Sonarr get_queue failed")

    series = get_series(settings)
    if series is not None:
        points.extend(series_points(series))
    else:
        logger.error("Sonarr get_series failed")

    diskspace = get_diskspace(settings)
    if diskspace is not None:
        points.extend(diskspace_points(diskspace))
    else:
        logger.error("Sonarr get_diskspace failed")

    calendar = get_calendar(settings)
    if calendar is not None:
        points.extend(calendar_points(calendar))
    else:
        logger.error("Sonarr get_calendar failed")

    return points
