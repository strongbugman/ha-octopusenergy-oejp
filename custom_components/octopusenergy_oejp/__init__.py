"""Home Assistant integration for Octopus Energy OEJP.

The package can also be imported by the standalone CLI in a plain Python
virtualenv that does not have Home Assistant installed.  Keep HA-only imports
inside the setup functions so ``python scripts/fetch_sensors.py`` can reuse the
API/model code without pulling in Home Assistant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import DOMAIN, PLATFORMS

if TYPE_CHECKING:  # pragma: no cover - typing only
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    from .coordinator import OctopusOejpDataUpdateCoordinator

    coordinator = OctopusOejpDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: "HomeAssistant", entry: "ConfigEntry") -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
