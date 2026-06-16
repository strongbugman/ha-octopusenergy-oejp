"""Prototype sensors for Octopus Energy OEJP discovery status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctopusOejpDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OctopusOejpDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OctopusOejpDiscoverySensor(coordinator, entry, "successful_endpoints", "Successful endpoints"),
            OctopusOejpDiscoverySensor(coordinator, entry, "failed_endpoints", "Failed endpoints"),
        ]
    )


class OctopusOejpDiscoverySensor(CoordinatorEntity[OctopusOejpDataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OctopusOejpDataUpdateCoordinator,
        entry: ConfigEntry,
        metric: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._metric = metric
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{metric}"

    @property
    def native_value(self) -> int | None:
        counts = (self.coordinator.data or {}).get("endpoint_counts", {})
        if self._metric == "successful_endpoints":
            return counts.get("successful")
        if self._metric == "failed_endpoints":
            return counts.get("failed")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "authenticated": data.get("authenticated"),
            "discovered": data.get("discovered"),
        }
