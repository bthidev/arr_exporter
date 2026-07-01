from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # InfluxDB
    influxdb_url: str
    influxdb_token: str
    influxdb_org: str
    influxdb_bucket: str

    # Tautulli
    tautulli_url: str
    tautulli_api_key: str

    # Sonarr
    sonarr_url: str
    sonarr_api_key: str

    # Radarr
    radarr_url: str
    radarr_api_key: str

    # App
    poll_interval_seconds: int = 60
    log_level: str = "INFO"
    health_port: int = 8000


def load_settings() -> Settings:
    return Settings()
