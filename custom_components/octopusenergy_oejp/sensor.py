"""Sensors for Octopus Energy OEJP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OctopusOejpDataUpdateCoordinator
from .models import (
    ACCESS_AUTHORIZED,
    AGGREGATE_PERIOD_THIS_MONTH,
    AGGREGATE_PERIOD_THIS_WEEK,
    AGGREGATE_PERIOD_TODAY,
    Account,
    ElectricitySupplyPoint,
    EnergySnapshot,
    aggregate_supply_point_half_hourly_readings,
)


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
    attributes_fn: Callable[[ElectricitySupplyPoint], dict[str, Any]]
    native_unit_of_measurement: str | None = None
    device_class: Any = None
    state_class: Any = None


def _empty_attributes(point: ElectricitySupplyPoint) -> dict[str, Any]:
    return {}


def _access_attributes(status: Any) -> dict[str, Any]:
    attributes: dict[str, Any] = {"field_name": status.field_name}
    if status.message:
        attributes["error_message"] = status.message
    if status.error_codes:
        attributes["error_codes"] = status.error_codes
    if status.error_paths:
        attributes["error_paths"] = status.error_paths
    return attributes


def _interval_access_attributes(point: ElectricitySupplyPoint) -> dict[str, Any]:
    return _access_attributes(point.interval_readings_access)


def _half_hourly_access_attributes(point: ElectricitySupplyPoint) -> dict[str, Any]:
    return _access_attributes(point.half_hourly_readings_access)


def _latest_interval_value(point: ElectricitySupplyPoint) -> Any:
    reading = point.latest_interval_reading
    return None if reading is None else reading.value


def _latest_interval_cost(point: ElectricitySupplyPoint) -> Any:
    reading = point.latest_interval_reading
    return None if reading is None else reading.cost_estimate


def _latest_interval_date(point: ElectricitySupplyPoint) -> str | None:
    reading = point.latest_interval_reading
    return None if reading is None else reading.reading_date or reading.start_at


def _latest_half_hourly_value(point: ElectricitySupplyPoint) -> Any:
    reading = point.latest_half_hourly_reading
    return None if reading is None else reading.value


def _latest_half_hourly_cost(point: ElectricitySupplyPoint) -> Any:
    reading = point.latest_half_hourly_reading
    return None if reading is None else reading.cost_estimate


def _latest_half_hourly_time(point: ElectricitySupplyPoint) -> str | None:
    reading = point.latest_half_hourly_reading
    return None if reading is None else reading.start_at


def _aggregate_state(point: ElectricitySupplyPoint, state: Any, reading_count: int) -> Any:
    if point.half_hourly_readings_access.status != ACCESS_AUTHORIZED and reading_count == 0:
        return None
    return state


def _aggregate_consumption_value(period: str) -> Callable[[ElectricitySupplyPoint], Any]:
    def value(point: ElectricitySupplyPoint) -> Any:
        aggregate = aggregate_supply_point_half_hourly_readings(point, period)
        return _aggregate_state(point, aggregate.total_consumption, aggregate.reading_count)

    return value


def _aggregate_cost_value(period: str) -> Callable[[ElectricitySupplyPoint], Any]:
    def value(point: ElectricitySupplyPoint) -> Any:
        aggregate = aggregate_supply_point_half_hourly_readings(point, period)
        return _aggregate_state(point, aggregate.total_cost, aggregate.reading_count)

    return value


def _aggregate_attributes(period: str) -> Callable[[ElectricitySupplyPoint], dict[str, Any]]:
    def attributes(point: ElectricitySupplyPoint) -> dict[str, Any]:
        aggregate = aggregate_supply_point_half_hourly_readings(point, period)
        return aggregate.as_attributes()

    return attributes


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
    SupplyPointSensorData("status", "Status", lambda p: p.status, _empty_attributes),
    SupplyPointSensorData("agreement_count", "Agreements", lambda p: len(p.agreements), _empty_attributes),
    SupplyPointSensorData("meter_count", "Meter Count", lambda p: p.meter_count, _empty_attributes),
    SupplyPointSensorData(
        "next_reading_date",
        "Next Reading Date",
        lambda p: p.next_reading_date,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "next_next_reading_date",
        "Next Next Reading Date",
        lambda p: p.next_next_reading_date,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "reading_date_day_of_month",
        "Reading Day Of Month",
        lambda p: p.reading_date_day_of_month,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_interval_reading_value",
        "Latest Interval Reading Value",
        _latest_interval_value,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_interval_reading_cost",
        "Latest Interval Reading Cost",
        _latest_interval_cost,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_interval_reading_date",
        "Latest Interval Reading Date",
        _latest_interval_date,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_half_hourly_reading_value",
        "Latest Half-Hour Reading Value",
        _latest_half_hourly_value,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_half_hourly_reading_cost",
        "Latest Half-Hour Reading Cost",
        _latest_half_hourly_cost,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "latest_half_hourly_reading_time",
        "Latest Half-Hour Reading Time",
        _latest_half_hourly_time,
        _empty_attributes,
    ),
    SupplyPointSensorData(
        "interval_readings_access",
        "Interval Readings Access",
        lambda p: p.interval_readings_access.status,
        _interval_access_attributes,
    ),
    SupplyPointSensorData(
        "half_hourly_readings_access",
        "Half-Hour Readings Access",
        lambda p: p.half_hourly_readings_access.status,
        _half_hourly_access_attributes,
    ),
    SupplyPointSensorData(
        "today_consumption",
        "Today Consumption",
        _aggregate_consumption_value(AGGREGATE_PERIOD_TODAY),
        _aggregate_attributes(AGGREGATE_PERIOD_TODAY),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SupplyPointSensorData(
        "today_cost",
        "Today Cost",
        _aggregate_cost_value(AGGREGATE_PERIOD_TODAY),
        _aggregate_attributes(AGGREGATE_PERIOD_TODAY),
        native_unit_of_measurement="JPY",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SupplyPointSensorData(
        "this_week_consumption",
        "This Week Consumption",
        _aggregate_consumption_value(AGGREGATE_PERIOD_THIS_WEEK),
        _aggregate_attributes(AGGREGATE_PERIOD_THIS_WEEK),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SupplyPointSensorData(
        "this_week_cost",
        "This Week Cost",
        _aggregate_cost_value(AGGREGATE_PERIOD_THIS_WEEK),
        _aggregate_attributes(AGGREGATE_PERIOD_THIS_WEEK),
        native_unit_of_measurement="JPY",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SupplyPointSensorData(
        "this_month_consumption",
        "This Month Consumption",
        _aggregate_consumption_value(AGGREGATE_PERIOD_THIS_MONTH),
        _aggregate_attributes(AGGREGATE_PERIOD_THIS_MONTH),
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SupplyPointSensorData(
        "this_month_cost",
        "This Month Cost",
        _aggregate_cost_value(AGGREGATE_PERIOD_THIS_MONTH),
        _aggregate_attributes(AGGREGATE_PERIOD_THIS_MONTH),
        native_unit_of_measurement="JPY",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
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
        self._attr_native_unit_of_measurement = sensor_data.native_unit_of_measurement
        self._attr_device_class = sensor_data.device_class
        self._attr_state_class = sensor_data.state_class
        self._value_fn = sensor_data.value_fn
        self._attributes_fn = sensor_data.attributes_fn

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
        attributes = {
            "meter_count": len(point.meters),
            "supply_point_fingerprint": self._point_fingerprint,
        }
        attributes.update(self._attributes_fn(point))
        return attributes
