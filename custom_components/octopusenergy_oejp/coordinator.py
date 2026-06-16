"""Data coordinator skeleton for Octopus Energy OEJP."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from octopusenergy_oejp_demo import OctopusOejpClient, async_discover_account_electricity_data

from .const import CONF_AUTH_PATH, CONF_BASE_URL, CONF_EMAIL, CONF_PASSWORD, DOMAIN

SCAN_INTERVAL = timedelta(minutes=15)
_LOGGER = logging.getLogger(__name__)


class OctopusOejpDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch a redacted discovery summary for prototype sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        data = entry.data
        auth_path = data.get(CONF_AUTH_PATH)
        self.client = OctopusOejpClient(
            email=data[CONF_EMAIL],
            password=data[CONF_PASSWORD],
            base_url=data.get(CONF_BASE_URL, "https://api.oejp-kraken.energy"),
            auth_paths=(auth_path,) if auth_path else None,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            report = await async_discover_account_electricity_data(
                self.client,
                max_pages=3,
                max_derived_requests=25,
            )
        except Exception as exc:  # noqa: BLE001
            raise UpdateFailed(str(exc)) from exc
        return report.summary()
