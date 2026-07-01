import json
from pathlib import Path

import pytest

from arr_exporter.config import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        influxdb_url="http://influxdb:8086",
        influxdb_token="test-token",
        influxdb_org="test-org",
        influxdb_bucket="test-bucket",
        tautulli_url="http://tautulli:8181",
        tautulli_api_key="tautulli-key",
        sonarr_url="http://sonarr:8989",
        sonarr_api_key="sonarr-key",
        radarr_url="http://radarr:7878",
        radarr_api_key="radarr-key",
        qbittorrent_url="http://qbittorrent:8080",
        qbittorrent_username="qbit-user",
        qbittorrent_password="qbit-pass",
        gluetun_control_url="http://gluetun:8000",
    )
