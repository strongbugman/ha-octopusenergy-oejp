"""Sensors for Octopus Energy OEJP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctopusOejpDataUpdateCoordinator
from .models import Account, ElectricitySupplyPoint, EnergySnapshot


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _safe_label(kind: str, value: str) -> str:
    return f"{kind} {_fingerprint(value)}"


@dataclass(frozen=True)
class SummarySensorData:
    key: str
    name: str
    value_fn: Callable[[EnergySnapshot], Any]


@dataclass(frozen=True)
class AccountSensorData:
    key: str
    name: str
    value_fn: Callable[[Account], Any]


@dataclass(frozen=True)
class SupplyPointSensorData:
    key: str
    name: str
    value_fn: Callable[[ElectricitySupplyPoint], Any]


SUMMARY_SENSORS: tuple[SummarySensorData, ...] = (
    SummarySensorData("account_count", "Account Count", lambda s: s.account_count),
    SummarySensorData("property_count", "Property Count", lambda s: s.property_count),
    SummarySensorData("supply_point_count", "Electricity Supply Points", lambda s: s.supply_point_count),
    SummarySensorData("bills_total", "Bills Total", lambda s: s.bills_total),
    SummarySensorData("transactions_total", "Transactions Total", lambda s: s.transactions_total),
    SummarySensorData("agreements_count", "Active Agreements", lambda s: s.active_agreement_count),
)

ACCOUNT_SENSORS: tuple[AccountSensorData, ...] = (
    AccountSensorData("balance", "Balance", lambda a: a.balance),
    AccountSensorData("status", "Status", lambda a: a.status),
    AccountSensorData("bills_total", "Bills Total", lambda a: a.bills_total),
    AccountSensorData("transactions_total", "Transactions Total", lambda a: a.transactions_total),
)

SUPPLY_POINT_SENSORS: tuple[SupplyPointSensorData, ...] = (
    SupplyPointSensorData("status", "Status", lambda p: p.status),
    SupplyPointSensorData("agreement_count", "Agreements", lambda p: len(p.agreements)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OctopusOejpDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        OctopusOejpSummarySensor(coordinator, entry, spec)
        for spec in SUMMARY_SENSORS
    ]

    snapshot: EnergySnapshot | None = coordinator.data
    if snapshot is not None:
        for account in snapshot.viewer.accounts:
            entities.extend(_account_sensors(coordinator, entry, account))

    async_add_entities(entities)


def _account_sensors(
    coordinator: OctopusOejpDataUpdateCoordinator,
    entry: ConfigEntry,
    account: Account,
) -> list[SensorEntity]:
    number = account.number
    sensors: list[SensorEntity] = [
        OctopusOejpAccountSensor(coordinator, entry, number, spec)
        for spec in ACCOUNT_SENSORS
    ]
    for prop in account.properties:
        for point in prop.electricity_supply_points:
            sensors.extend(_supply_point_sensors(coordinator, entry, number, point))
    return sensors


def _supply_point_sensors(
    coordinator: OctopusOejpDataUpdateCoordinator,
    entry: ConfigEntry,
    account_number: str,
    point: ElectricitySupplyPoint,
) -> list[SensorEntity]:
    label = _safe_label("Supply Point", point.id)
    return [
        OctopusOejpSupplyPointSensor(
            coordinator,
            entry,
            account_number,
            point.id,
            spec,
            f"{label} {spec.name}",
        )
        for spec in SUPPLY_POINT_SENSORS
    ]


class OctopusOejpSummarySensor(
    CoordinatorEntity[OctopusOejpDataUpdateCoordinator], SensorEntity
):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: OctopusOejpDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_data: SummarySensorData,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = sensor_data.name
        self._attr_unique_id = f"{entry.entry_id}_{sensor_data.key}"
        self._value_fn = sensor_data.value_fn

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        return self._value_fn(self.coordinator.data)


class OctopusOejpAccountSensor(
    CoordinatorEntity[OctopusOejpDataUpdateCoordinator], SensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OctopusOejpDataUpdateCoordinator,
        entry: ConfigEntry,
        account_number: str,
        sensor_data: AccountSensorData,
    ) -> None:
        super().__init__(coordinator)
        account_fingerprint = _fingerprint(account_number)
        self._account_number = account_number
        self._account_fingerprint = account_fingerprint
        self._metric = sensor_data.key
        self._attr_name = f"Account {account_fingerprint} {sensor_data.name}"
        self._attr_unique_id = f"{entry.entry_id}_account_{account_fingerprint}_{sensor_data.key}"
        self._value_fn = sensor_data.value_fn

    def _find_account(self) -> Account | None:
        if self.coordinator.data is None:
            return None
        for account in self.coordinator.data.viewer.accounts:
            if account.number == self._account_number:
                return account
        return None

    @property
    def native_value(self) -> Any:
        account = self._find_account()
        return None if account is None else self._value_fn(account)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._metric != "balance":
            return {}
        account = self._find_account()
        if account is None:
            return {}
        return {"account_fingerprint": self._account_fingerprint, "status": account.status}


class OctopusOejpSupplyPointSensor(
    CoordinatorEntity[OctopusOejpDataUpdateCoordinator], SensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OctopusOejpDataUpdateCoordinator,
        entry: ConfigEntry,
        account_number: str,
        point_id: str,
        sensor_data: SupplyPointSensorData,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        account_fingerprint = _fingerprint(account_number)
        point_fingerprint = _fingerprint(point_id)
        self._account_number = account_number
        self._point_id = point_id
        self._point_fingerprint = point_fingerprint
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_account_{account_fingerprint}_supply_{point_fingerprint}_{sensor_data.key}"
        self._value_fn = sensor_data.value_fn

    def _find_point(self) -> ElectricitySupplyPoint | None:
        if self.coordinator.data is None:
            return None
        for account in self.coordinator.data.viewer.accounts:
            if account.number == self._account_number:
                for prop in account.properties:
                    for point in prop.electricity_supply_points:
                        if point.id == self._point_id:
                            return point
        return None

    @property
    def native_value(self) -> Any:
        point = self._find_point()
        return None if point is None else self._value_fn(point)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self._find_point()
        if point is None:
            return {}
        return {"meter_count": len(point.meters), "supply_point_fingerprint": self._point_fingerprint}
