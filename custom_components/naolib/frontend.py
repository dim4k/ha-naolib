"""Serve the Naolib loader so that an outdated page still gets the current card.

After an update, Home Assistant's service worker or the mobile apps can keep
an old page, hence an old versioned loader URL and an outdated card, until
their frontend cache is reset by hand. The loader is served at a fixed URL
under /api/, which the service worker always fetches from the network (it
serves any other URL from its cache first, whatever the cache headers say),
with the card's content hash stamped in: an outdated page still runs the
current loader, which imports the card under a URL that changes with its
content.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

WWW_PATH = Path(__file__).parent / "www"
LOADER_URL = "/api/naolib/loader.js"
CARD_FILENAME = "naolib-card.js"
# Placeholder of the loader bundle, replaced by the card's hash when served.
CARD_HASH_PLACEHOLDER = "__NAOLIB_CARD_HASH__"


class NaolibLoaderView(HomeAssistantView):
    """Serve the loader uncached, with the hash of the current card in it."""

    url = LOADER_URL
    name = "naolib:loader"
    requires_auth = False

    def __init__(self, body: str) -> None:
        """Keep the loader, already stamped with the card's hash."""
        self._body = body

    async def get(self, request: web.Request) -> web.Response:
        """Return the loader, to be revalidated on every page load."""
        return web.Response(
            text=self._body,
            content_type="text/javascript",
            headers={"Cache-Control": "no-cache"},
        )


def stamped_loader(www: Path, loader_filename: str) -> str:
    """Read the loader and stamp the card's content hash into it.

    This performs blocking file IO and must be called from an executor.
    """
    try:
        card = (www / CARD_FILENAME).read_bytes()
        loader = (www / loader_filename).read_text(encoding="utf-8")
    except OSError as exception:
        _LOGGER.error("Could not read the Naolib card files: %s", exception)
        return ""
    card_hash = hashlib.sha256(card).hexdigest()[:16]
    return loader.replace(CARD_HASH_PLACEHOLDER, card_hash)


async def async_register_loader(hass: HomeAssistant, loader_filename: str) -> str:
    """Serve the stamped loader and return its URL."""
    body = await hass.async_add_executor_job(stamped_loader, WWW_PATH, loader_filename)
    hass.http.register_view(NaolibLoaderView(body))
    return LOADER_URL
