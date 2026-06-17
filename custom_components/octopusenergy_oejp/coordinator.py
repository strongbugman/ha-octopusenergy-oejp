"""Data coordinator for Octopus Energy OEJP."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GraphQLClient, GraphQLError, GraphQLOptionalResult
from .const import CONF_BASE_URL, CONF_EMAIL, CONF_PASSWORD, DEFAULT_BASE_URL, DOMAIN
from .models import (
    AccessStatus,
    EnergySnapshot,
    access_status_from_graphql_error,
    apply_half_hourly_readings,
    apply_interval_readings,
    parse_energy_snapshot,
)

SCAN_INTERVAL = timedelta(minutes=15)
RECENT_CONSUMPTION_WINDOW = timedelta(days=7)
JST = timezone(timedelta(hours=9))
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

    def _obtain_access_token(self) -> str:
        return self._client.obtain_token(email=self._email, password=self._password).access_token

    def _fetch_base_snapshot(self, access_token: str) -> dict:
        return self._client.viewer_energy_snapshot(token=access_token)

    def _fetch_interval_readings(
        self,
        access_token: str,
        account_number: str,
    ) -> GraphQLOptionalResult:
        return self._client.account_interval_readings(
            token=access_token,
            account_number=account_number,
        )

    def _fetch_half_hourly_readings(
        self,
        access_token: str,
        account_number: str,
        from_datetime: str,
        to_datetime: str,
    ) -> GraphQLOptionalResult:
        return self._client.account_half_hourly_readings(
            token=access_token,
            account_number=account_number,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    @staticmethod
    def _recent_consumption_range() -> tuple[str, str]:
        to_datetime = datetime.now(JST).replace(microsecond=0)
        from_datetime = to_datetime - RECENT_CONSUMPTION_WINDOW
        return from_datetime.isoformat(), to_datetime.isoformat()

    @staticmethod
    def _access_status(
        field_name: str,
        result: GraphQLOptionalResult,
    ) -> AccessStatus:
        if result.error is None:
            return AccessStatus.authorized(field_name)
        return access_status_from_graphql_error(field_name, result.error)

    async def _async_update_data(self) -> EnergySnapshot:
        try:
            access_token = await self.hass.async_add_executor_job(self._obtain_access_token)
            raw = await self.hass.async_add_executor_job(self._fetch_base_snapshot, access_token)
        except GraphQLError as exc:
            raise UpdateFailed(str(exc)) from exc

        snapshot = parse_energy_snapshot(raw)
        from_datetime, to_datetime = self._recent_consumption_range()
        for account in snapshot.viewer.accounts:
            interval_result = await self.hass.async_add_executor_job(
                self._fetch_interval_readings,
                access_token,
                account.number,
            )
            apply_interval_readings(
                snapshot,
                interval_result.payload,
                self._access_status("intervalReadings", interval_result),
                account_number=account.number,
            )

            half_hourly_result = await self.hass.async_add_executor_job(
                self._fetch_half_hourly_readings,
                access_token,
                account.number,
                from_datetime,
                to_datetime,
            )
            apply_half_hourly_readings(
                snapshot,
                half_hourly_result.payload,
                self._access_status("halfHourlyReadings", half_hourly_result),
                account_number=account.number,
            )
        return snapshot
