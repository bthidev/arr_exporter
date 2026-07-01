import logging
from datetime import datetime, timedelta, timezone

from influxdb_client import Point

from arr_exporter.config import Settings
from arr_exporter.http import get_json

logger = logging.getLogger(__name__)

CALENDAR_DAYS_AHEAD = 7


def _get(settings: Settings, path: str, params: dict | None = None) -> dict | list | None:
    url = f"{settings.radarr_url.rstrip('/')}/api/v3/{path}"
    headers = {"X-Api-Key": settings.radarr_api_key}
    return get_json(url, params=params, headers=headers)


def get_queue(settings: Settings) -> dict | None:
    return _get(settings, "queue", params={"pageSize": 250})


def get_movies(settings: Settings) -> list | None:
    return _get(settings, "movie")


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

    point = Point("radarr_queue").tag("service", "radarr").field("total", len(records))
    for status, count in status_counts.items():
        point.field(f"status_{status}", count)
    return [point]


def movie_points(movies: list) -> list[Point]:
    monitored = sum(1 for m in movies if m.get("monitored"))
    missing = sum(1 for m in movies if m.get("monitored") and not m.get("hasFile"))

    point = (
        Point("radarr_movies")
        .tag("service", "radarr")
        .field("movie_count", len(movies))
        .field("monitored", monitored)
        .field("missing", missing)
    )
    return [point]


def diskspace_points(diskspace: list) -> list[Point]:
    points = []
    for disk in diskspace:
        point = (
            Point("radarr_diskspace")
            .tag("service", "radarr")
            .tag("path", disk.get("path", "unknown"))
            .field("free_bytes", int(disk.get("freeSpace", 0) or 0))
            .field("total_bytes", int(disk.get("totalSpace", 0) or 0))
        )
        points.append(point)
    return points


def calendar_points(calendar: list) -> list[Point]:
    point = Point("radarr_calendar").tag("service", "radarr").field("upcoming_count", len(calendar))
    return [point]


def collect(settings: Settings) -> list[Point]:
    points: list[Point] = []

    queue = get_queue(settings)
    if queue is not None:
        points.extend(queue_points(queue))
    else:
        logger.error("Radarr get_queue failed")

    movies = get_movies(settings)
    if movies is not None:
        points.extend(movie_points(movies))
    else:
        logger.error("Radarr get_movies failed")

    diskspace = get_diskspace(settings)
    if diskspace is not None:
        points.extend(diskspace_points(diskspace))
    else:
        logger.error("Radarr get_diskspace failed")

    calendar = get_calendar(settings)
    if calendar is not None:
        points.extend(calendar_points(calendar))
    else:
        logger.error("Radarr get_calendar failed")

    return points
