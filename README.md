# arr_exporter

Small Python exporter that polls **Tautulli**, **Sonarr** and **Radarr** on a
fixed interval and writes the collected metrics to **InfluxDB v2** using the
official client (Line Protocol over the v2 write API).

No Prometheus, no scraping — this is a push-based exporter: it fetches from
each `*arr` API, builds `Point`s, and writes them straight to your InfluxDB
bucket.

## Requirements

- An existing InfluxDB v2 instance (org + bucket + API token already created)
- Tautulli, Sonarr and Radarr reachable over HTTP with their API keys
- Python 3.12+ (for the systemd/LXC route) or Docker (for the Portainer route)

## Installation

### Option A — Docker / Portainer

1. Copy `.env.example` to `.env` and fill in the values.
2. Make sure the container can reach Tautulli/Sonarr/Radarr/InfluxDB — either
   put it on the same Docker network as those services, or point the
   `*_URL` variables at an internal hostname (e.g. via Nginx Proxy Manager).
3. Deploy the stack:

   ```bash
   docker compose up -d --build
   ```

   In Portainer: Stacks → Add stack → paste `docker-compose.yml` → set the
   environment variables (or upload `.env`) → Deploy.

4. Check health: `curl http://<host>:8000/health` should return `200`.

### Option B — LXC / systemd

1. On the LXC (Debian/Ubuntu base), install Python 3.12+ and clone this repo.
2. Create a venv and install dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   cp .env.example .env   # then edit it
   ```

3. Create `/etc/systemd/system/arr_exporter.service`:

   ```ini
   [Unit]
   Description=arr_exporter
   After=network-online.target

   [Service]
   Type=simple
   WorkingDirectory=/opt/arr_exporter
   EnvironmentFile=/opt/arr_exporter/.env
   ExecStart=/opt/arr_exporter/.venv/bin/python -m arr_exporter.main
   Restart=on-failure
   RestartSec=5
   User=arr_exporter

   [Install]
   WantedBy=multi-user.target
   ```

4. Enable and start:

   ```bash
   systemctl daemon-reload
   systemctl enable --now arr_exporter
   ```

## Configuration

All configuration is via environment variables (see `.env.example`):

| Variable                 | Description                                  | Default |
|---------------------------|-----------------------------------------------|---------|
| `INFLUXDB_URL`            | InfluxDB v2 base URL                          | —       |
| `INFLUXDB_TOKEN`          | InfluxDB v2 API token                         | —       |
| `INFLUXDB_ORG`            | InfluxDB v2 organization                      | —       |
| `INFLUXDB_BUCKET`         | InfluxDB v2 bucket                            | —       |
| `TAUTULLI_URL`            | Tautulli base URL                             | —       |
| `TAUTULLI_API_KEY`        | Tautulli API key                              | —       |
| `SONARR_URL`              | Sonarr base URL                               | —       |
| `SONARR_API_KEY`          | Sonarr API key                                | —       |
| `RADARR_URL`              | Radarr base URL                               | —       |
| `RADARR_API_KEY`          | Radarr API key                                | —       |
| `POLL_INTERVAL_SECONDS`   | Seconds between collection cycles             | `60`    |
| `LOG_LEVEL`               | Python logging level                          | `INFO`  |
| `HEALTH_PORT`             | Port for the `/health` HTTP endpoint          | `8000`  |

A failing collector (timeout, 401, service down) is logged and skipped —
the other collectors and the next poll cycle are unaffected.

## Exported metrics

| Measurement          | Tags                              | Fields                                                                 |
|-----------------------|------------------------------------|-------------------------------------------------------------------------|
| `tautulli_activity`   | `service`                          | `stream_count`, `stream_count_direct_play`, `stream_count_direct_stream`, `stream_count_transcode`, `total_bandwidth`, `lan_bandwidth`, `wan_bandwidth` |
| `tautulli_library`    | `service`, `section_name`, `section_type` | `count`, `parent_count`, `child_count`                            |
| `tautulli_history`    | `service`, `user`                  | `full_title` (last 10 history entries, one point per entry)             |
| `sonarr_queue`        | `service`                           | `total`, `status_<status>` (one field per distinct queue status)        |
| `sonarr_series`       | `service`                           | `series_count`, `episodes_monitored`, `episodes_missing`                |
| `sonarr_diskspace`    | `service`, `path`                   | `free_bytes`, `total_bytes`                                             |
| `sonarr_calendar`     | `service`                           | `upcoming_count` (next 7 days)                                           |
| `radarr_queue`        | `service`                           | `total`, `status_<status>` (one field per distinct queue status)        |
| `radarr_movies`       | `service`                           | `movie_count`, `monitored`, `missing`                                    |
| `radarr_diskspace`    | `service`, `path`                   | `free_bytes`, `total_bytes`                                             |
| `radarr_calendar`     | `service`                           | `upcoming_count` (next 7 days)                                           |

## Verifying data in InfluxDB

Flux query to check that points are arriving (adjust bucket name):

```flux
from(bucket: "media")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] =~ /^(tautulli|sonarr|radarr)_/)
  |> filter(fn: (r) => r["service"] == "sonarr" or r["service"] == "radarr" or r["service"] == "tautulli")
```

## Health check

The exporter exposes `GET /health` on `HEALTH_PORT` (default `8000`):
returns `200` if a collection cycle ran within the last
`3 * POLL_INTERVAL_SECONDS`, `503` otherwise. Useful for Docker healthchecks
or an external uptime monitor.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

All tests mock HTTP calls (via `responses`) — no real network access is made.
