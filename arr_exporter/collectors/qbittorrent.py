import logging
import time

import requests
from influxdb_client import Point

from arr_exporter.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

# States are grouped so the number of fields stays fixed regardless of how
# many distinct torrent states qBittorrent reports.
STATE_GROUPS = {
    "downloading": {"downloading", "forcedDL", "metaDL", "forcedMetaDL"},
    "seeding": {"uploading", "forcedUP"},
    "stalled_dl": {"stalledDL"},
    "stalled_up": {"stalledUP"},
    "paused": {"pausedDL", "pausedUP"},
    "error": {"error", "missingFiles"},
    "checking": {"checkingDL", "checkingUP", "checkingResumeData"},
}

DETAIL_STATES = {"error", "missingFiles"}
STALLED_DL_DETAIL_THRESHOLD_SECONDS = 600
DETAIL_NAME_MAX_LENGTH = 64

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def reset_session() -> None:
    global _session
    _session = None


def _login(settings: Settings) -> bool:
    session = _get_session()
    url = f"{settings.qbittorrent_url.rstrip('/')}/api/v2/auth/login"
    try:
        resp = session.post(
            url,
            data={
                "username": settings.qbittorrent_username,
                "password": settings.qbittorrent_password,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        logger.warning("qBittorrent login to %s failed", url, exc_info=True)
        return False
    return resp.text.strip() == "Ok."


def get_maindata(settings: Settings) -> dict | None:
    session = _get_session()
    url = f"{settings.qbittorrent_url.rstrip('/')}/api/v2/sync/maindata"

    for attempt in range(2):
        try:
            resp = session.get(url, timeout=DEFAULT_TIMEOUT)
        except requests.exceptions.RequestException:
            logger.warning("Request to %s failed", url, exc_info=True)
            return None

        if resp.status_code == 403 and attempt == 0:
            logger.info("qBittorrent session expired or missing, re-authenticating")
            if not _login(settings):
                return None
            continue

        try:
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            logger.warning("Request to %s failed", url, exc_info=True)
            return None
        return resp.json()

    return None


def server_state_points(state: dict) -> list[Point]:
    try:
        global_ratio = float(state.get("global_ratio", 0) or 0)
    except (TypeError, ValueError):
        global_ratio = 0.0

    point = (
        Point("qbittorrent_transfer")
        .tag("service", "qbittorrent")
        .tag("connection_status", state.get("connection_status", "unknown"))
        .field("dl_speed", int(state.get("dl_info_speed", 0) or 0))
        .field("up_speed", int(state.get("up_info_speed", 0) or 0))
        .field("dl_data", int(state.get("dl_info_data", 0) or 0))
        .field("up_data", int(state.get("up_info_data", 0) or 0))
        .field("free_space_on_disk", int(state.get("free_space_on_disk", 0) or 0))
        .field("global_ratio", global_ratio)
        .field("dht_nodes", int(state.get("dht_nodes", 0) or 0))
    )
    return [point]


def torrent_summary_points(torrents: dict) -> list[Point]:
    counts = dict.fromkeys(STATE_GROUPS, 0)
    for torrent in torrents.values():
        state = torrent.get("state", "unknown")
        for field, states in STATE_GROUPS.items():
            if state in states:
                counts[field] += 1
                break

    point = Point("qbittorrent_torrents").tag("service", "qbittorrent").field("total", len(torrents))
    for field, count in counts.items():
        point.field(field, count)
    return [point]


def _needs_detail(torrent: dict) -> bool:
    state = torrent.get("state")
    if state in DETAIL_STATES:
        return True
    if state == "stalledDL":
        last_activity = torrent.get("last_activity")
        if last_activity is None or last_activity <= 0:
            return True
        return (time.time() - last_activity) > STALLED_DL_DETAIL_THRESHOLD_SECONDS
    return False


def torrent_detail_points(torrents: dict) -> list[Point]:
    points = []
    for torrent in torrents.values():
        if not _needs_detail(torrent):
            continue

        name = str(torrent.get("name", "unknown"))[:DETAIL_NAME_MAX_LENGTH]
        point = (
            Point("qbittorrent_torrent_detail")
            .tag("service", "qbittorrent")
            .tag("name", name)
            .tag("state", torrent.get("state", "unknown"))
            .tag("category", torrent.get("category") or "none")
            .field("progress", float(torrent.get("progress", 0) or 0))
            .field("num_seeds", int(torrent.get("num_seeds", 0) or 0))
            .field("num_leechs", int(torrent.get("num_leechs", 0) or 0))
            .field("eta", int(torrent.get("eta", 0) or 0))
        )
        points.append(point)
    return points


def collect(settings: Settings) -> list[Point]:
    points: list[Point] = []

    maindata = get_maindata(settings)
    if maindata is None:
        logger.error("qBittorrent get_maindata failed")
        return points

    server_state = maindata.get("server_state", {})
    if server_state:
        points.extend(server_state_points(server_state))

    torrents = maindata.get("torrents", {})
    points.extend(torrent_summary_points(torrents))
    points.extend(torrent_detail_points(torrents))

    return points
