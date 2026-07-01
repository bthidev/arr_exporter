import logging

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from arr_exporter.config import Settings

logger = logging.getLogger(__name__)


class InfluxWriter:
    def __init__(self, settings: Settings):
        self._client = InfluxDBClient(
            url=settings.influxdb_url,
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self._bucket = settings.influxdb_bucket
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write(self, points: list[Point]) -> None:
        if not points:
            return
        try:
            self._write_api.write(bucket=self._bucket, record=points)
        except Exception:
            logger.exception("Failed to write %d point(s) to InfluxDB", len(points))

    def close(self) -> None:
        self._write_api.close()
        self._client.close()
