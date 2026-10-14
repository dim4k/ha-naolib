"""Tests for the uncached loader serving the current card."""

import re
from unittest.mock import patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.naolib.const import (
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
)
from custom_components.naolib.frontend import stamped_loader


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


async def test_the_loader_is_served_uncached_with_the_card_hash(
    hass: HomeAssistant, hass_client
) -> None:
    """The loader URL is fixed and uncached, the card URL carries its hash."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="STOP1",
        data={CONF_STOP_CODE: "STOP1", CONF_STOP_LABEL: "A", CONF_QUAYS: ["Q1"]},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.naolib.coordinator.NaolibApiClient"
            ".async_get_all_departures",
            return_value={},
        ),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get("/api/naolib/loader.js")
    body = await response.text()

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-cache"
    assert "__NAOLIB_CARD_HASH__" not in body
    assert re.search(r'CARD_URL\.search = "\?v=[0-9a-f]{16}"', body)


def test_missing_card_files_are_tolerated(tmp_path) -> None:
    """Without the built files the loader is empty instead of failing setup."""
    assert stamped_loader(tmp_path, "naolib-loader.js") == ""
