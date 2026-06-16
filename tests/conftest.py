"""Pytest configuration: HA stubs + shared sample data."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any


def _install_ha_stubs() -> None:
    """Install minimal homeassistant stubs so custom_components imports succeed."""
    if "homeassistant" in sys.modules:
        return

    class _Generic:
        def __class_getitem__(cls, item):
            return cls

    class UpdateFailed(Exception):
        pass

    class DataUpdateCoordinator(_Generic):
        def __init__(self, hass, logger, *, name, update_interval=None):
            self.hass = hass
            self.data = None

    class CoordinatorEntity(_Generic):
        def __init__(self, coordinator):
            self.coordinator = coordinator

    class SensorEntity:
        _attr_has_entity_name: bool = False
        _attr_name: str | None = None
        _attr_unique_id: str | None = None
        _attr_state_class: Any = None

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    class ConfigEntry:
        def __init__(self, entry_id: str = "test-entry-id", data: dict | None = None):
            self.entry_id = entry_id
            self.data = data or {}

    class ConfigFlow:
        def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)

    class HomeAssistant:
        pass

    class FlowResult(dict):
        pass

    stubs: dict[str, dict[str, Any]] = {
        "homeassistant": {},
        "homeassistant.config_entries": {
            "ConfigEntry": ConfigEntry,
            "ConfigFlow": ConfigFlow,
        },
        "homeassistant.core": {"HomeAssistant": HomeAssistant},
        "homeassistant.const": {"CONF_PASSWORD": "password"},
        "homeassistant.helpers": {},
        "homeassistant.helpers.update_coordinator": {
            "DataUpdateCoordinator": DataUpdateCoordinator,
            "UpdateFailed": UpdateFailed,
            "CoordinatorEntity": CoordinatorEntity,
        },
        "homeassistant.helpers.entity_platform": {"AddEntitiesCallback": Any},
        "homeassistant.components": {},
        "homeassistant.components.sensor": {
            "SensorEntity": SensorEntity,
            "SensorStateClass": SensorStateClass,
        },
        "homeassistant.data_entry_flow": {"FlowResult": FlowResult},
    }
    for mod_name, attrs in stubs.items():
        mod = ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[mod_name] = mod

    # Also make `from homeassistant import config_entries` work
    ha_mod = sys.modules["homeassistant"]
    ha_mod.config_entries = sys.modules["homeassistant.config_entries"]  # type: ignore[attr-defined]

    if "voluptuous" not in sys.modules:
        vol = ModuleType("voluptuous")
        vol.Schema = lambda x: x  # type: ignore[attr-defined]
        vol.Required = lambda k, **kw: k  # type: ignore[attr-defined]
        vol.Optional = lambda k, **kw: k  # type: ignore[attr-defined]
        sys.modules["voluptuous"] = vol


_install_ha_stubs()


# ---------------------------------------------------------------------------
# Shared sample GraphQL response data
# ---------------------------------------------------------------------------

SAMPLE_SNAPSHOT_RESPONSE: dict[str, Any] = {
    "data": {
        "viewer": {
            "id": "VWR-001",
            "accounts": [
                {
                    "number": "A-1234567",
                    "status": "ACTIVE",
                    "balance": 1500,
                    "transactions": {
                        "totalCount": 42,
                        "edges": [
                            {
                                "node": {
                                    "id": "T-001",
                                    "postedDate": "2024-01-15",
                                    "amount": -500,
                                    "title": "Payment",
                                }
                            },
                        ],
                    },
                    "bills": {
                        "totalCount": 12,
                        "edges": [{"node": {"id": "B-001"}}],
                    },
                    "properties": [
                        {
                            "id": "P-001",
                            "postcode": "100-0001",
                            "address": "Tokyo, Chiyoda 1-1",
                            "electricitySupplyPoints": [
                                {
                                    "id": "ESP-001",
                                    "spin": "SP-0001",
                                    "status": "ACTIVE",
                                    "meters": [{"serialNumber": "M-0001"}],
                                    "agreements": [
                                        {
                                            "id": "AGR-001",
                                            "validFrom": "2023-04-01",
                                            "validTo": None,
                                            "product": {"__typename": "HalfHourlyTariff"},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "marketSupplyAgreements": {
                        "totalCount": 2,
                        "edges": [
                            {
                                "node": {
                                    "id": "MSA-001",
                                    "validFrom": "2023-04-01",
                                    "validTo": None,
                                    "product": {"__typename": "OctogonerTariff"},
                                }
                            }
                        ],
                    },
                }
            ],
        }
    }
}
