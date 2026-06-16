"""Data coordinator for Octopus Energy OEJP."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GraphQLClient, GraphQLError
from .const import CONF_BASE_URL, CONF_EMAIL, CONF_PASSWORD, DEFAULT_BASE_URL, DOMAIN
from .models import EnergySnapshot, parse_energy_snapshot

SCAN_INTERVAL = timedelta(minutes=15)
_LOGGER = logging.getLogger(__name__)


class OctopusOejpDataUpdateCoordinator(DataUpdateCoordinator[EnergySnapshot]):
    """Fetch and parse the OEJP energy snapshot every 15 minutes."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry
        data = entry.data
        base = data.get(CONF_BASE_URL, DEFAULT_BASE_URL).rstrip("/")
        graphql_url = base + "/v1/graphql/"
        self._client = GraphQLClient(url=graphql_url)
        self._email: str = data[CONF_EMAIL]
        self._password: str = data[CONF_PASSWORD]

    def _fetch(self) -> dict:
        return self._client.fetch_snapshot(email=self._email, password=self._password)

    async def _async_update_data(self) -> EnergySnapshot:
        try:
            raw = await self.hass.async_add_executor_job(self._fetch)
            return parse_energy_snapshot(raw)
        except GraphQLError as exc:
            raise UpdateFailed(str(exc)) from exc
