import logging
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from arr_exporter.collectors import radarr, sonarr, tautulli
from arr_exporter.config import Settings, load_settings
from arr_exporter.influx import InfluxWriter

logger = logging.getLogger(__name__)

_last_tick = 0.0
_stop_event = threading.Event()

COLLECTORS = {
    "tautulli": tautulli.collect,
    "sonarr": sonarr.collect,
    "radarr": radarr.collect,
}


class HealthHandler(BaseHTTPRequestHandler):
    max_staleness_seconds = 300

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        stale = (time.time() - _last_tick) > self.max_staleness_seconds
        if _last_tick == 0.0 or stale:
            self.send_response(503)
        else:
            self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        pass


def start_health_server(port: int) -> ThreadingHTTPServer:
    HealthHandler.max_staleness_seconds = 300
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server listening on :%d/health", port)
    return server


def run_collectors(settings: Settings, writer: InfluxWriter) -> None:
    for name, collect in COLLECTORS.items():
        try:
            points = collect(settings)
            writer.write(points)
            logger.debug("Collected %d point(s) from %s", len(points), name)
        except Exception:
            logger.exception("Collector %s raised an unexpected error", name)


def _handle_signal(signum, frame):
    logger.info("Received signal %d, shutting down", signum)
    _stop_event.set()


def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    HealthHandler.max_staleness_seconds = settings.poll_interval_seconds * 3
    start_health_server(settings.health_port)

    writer = InfluxWriter(settings)
    logger.info("Starting arr_exporter, polling every %ds", settings.poll_interval_seconds)

    global _last_tick
    try:
        while not _stop_event.is_set():
            run_collectors(settings, writer)
            _last_tick = time.time()
            _stop_event.wait(settings.poll_interval_seconds)
    finally:
        writer.close()


if __name__ == "__main__":
    main()
