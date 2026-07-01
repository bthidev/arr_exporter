import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10


def get_json(url: str, params: dict | None = None, headers: dict | None = None) -> dict | None:
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        logger.warning("Request to %s failed", url, exc_info=True)
        return None
