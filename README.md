# arr_exporter

Small Python exporter that polls **Tautulli**, **Sonarr**, **Radarr**,
**qBittorrent** and **gluetun** (VPN) on a fixed interval and writes the
collected metrics to **InfluxDB v2** using the official client (Line Protocol
over the v2 write API).

No Prometheus, no scraping — this is a push-based exporter: it fetches from
each `*arr` API, builds `Point`s, and writes them straight to your InfluxDB
bucket.

## Requirements

- An existing InfluxDB v2 instance (org + bucket + API token already created)
- Tautulli, Sonarr and Radarr reachable over HTTP with their API keys
- qBittorrent reachable over HTTP with its WebUI credentials
- gluetun reachable over HTTP with its control server enabled
- Python 3.12+ (for the systemd/LXC route) or Docker (for the Portainer route)

## Installation

### Option A — Docker / Portainer

1. Copy `.env.example` to `.env` and fill in the values.
2. Make sure the container can reach Tautulli/Sonarr/Radarr/InfluxDB — either
   put it on the same Docker network as those services, or point the
   `*_URL` variables at an internal hostname (e.g. via Nginx Proxy Manager).
3. Deploy the stack. By default `docker-compose.yml` pulls the image built by
   CI (`ghcr.io/bthidev/arr_exporter:latest`); uncomment `build: .` instead if
   you want to build it locally:

   ```bash
   docker compose up -d
   ```

   In Portainer: Stacks → Add stack → paste `docker-compose.yml` → set the
   environment variables (or upload `.env`) → Deploy.

4. Check health: `curl http://<host>:8000/health` should return `200`.

The image is built from a multi-stage `Dockerfile` (`python:3.12-alpine`
builder + runtime, no compiler in the final layer) and published by
[`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml)
to GitHub Container Registry on every push to `main` and on version tags
(`v*`). Pull requests only build the image to validate the Dockerfile, they
don't push.

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
| `QBITTORRENT_URL`         | qBittorrent WebUI base URL                    | —       |
| `QBITTORRENT_USERNAME`    | qBittorrent WebUI username                    | —       |
| `QBITTORRENT_PASSWORD`    | qBittorrent WebUI password                    | —       |
| `GLUETUN_CONTROL_URL`     | gluetun control server base URL               | —       |
| `HOME_WAN_IP`             | Home WAN IP, optional, enables VPN leak detection | —   |
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
| `qbittorrent_transfer`| `service`, `connection_status`      | `dl_speed`, `up_speed`, `dl_data`, `up_data`, `free_space_on_disk`, `global_ratio`, `dht_nodes` |
| `qbittorrent_torrents`| `service`                           | `total`, `downloading`, `seeding`, `stalled_dl`, `stalled_up`, `paused`, `error`, `checking` |
| `qbittorrent_torrent_detail` | `service`, `name`, `state`, `category` | `progress`, `num_seeds`, `num_leechs`, `eta` (one point per torrent in `error`, `missingFiles`, or `stalledDL` for more than 10 minutes — not written for healthy torrents to keep cardinality low) |
| `gluetun_vpn`         | `service`, `protocol`               | `tunnel_up` (1/0), `public_ip` (string field, not a tag), `leak_detected` (bool, only present when `HOME_WAN_IP` is set) |

## Verifying data in InfluxDB

Flux query to check that points are arriving (adjust bucket name):

```flux
from(bucket: "media")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] =~ /^(tautulli|sonarr|radarr|qbittorrent|gluetun)_/)
  |> filter(fn: (r) => r["service"] == "sonarr" or r["service"] == "radarr" or r["service"] == "tautulli" or r["service"] == "qbittorrent" or r["service"] == "gluetun")
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
