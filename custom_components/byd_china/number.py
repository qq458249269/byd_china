"""Number entities for BYD Vehicle."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.vehicle import Vehicle

from .const import (
    AC_TEMP_MAX,
    AC_TEMP_MIN,
    AC_TEMP_STEP,
    CONF_AC_TEMPERATURE,
    CONF_GPS_POLL_INTERVAL,
    CONF_POLL_INTERVAL,
    DEFAULT_AC_TEMPERATURE,
    DOMAIN,
    MAX_GPS_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_GPS_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)
from .coordinator import BydDataUpdateCoordinator, BydGpsUpdateCoordinator
from .entity import BydVehicleEntity

_LOGGER = logging.getLogger(__name__)


def _hours_to_sec(h: float) -> int:
    return max(1, int(h * 3600))


def _sec_to_hours(s: int) -> float:
    return round(s / 3600, 1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD number entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, BydDataUpdateCoordinator] = data["coordinators"]
    gps_coordinators: dict[str, BydGpsUpdateCoordinator] = data.get(
        "gps_coordinators", {}
    )

    entities: list[NumberEntity] = []
    for vin, coordinator in coordinators.items():
        vehicle = coordinator.vehicle
        entities.append(
            BydRealtimePollIntervalNumber(hass, entry, coordinator, vin, vehicle)
        )
        entities.append(
            BydAcTemperatureNumber(hass, entry, coordinator, vin, vehicle)
        )

        gps_coordinator = gps_coordinators.get(vin)
        if gps_coordinator is not None:
            entities.append(
                BydGpsPollIntervalNumber(
                    hass,
                    entry,
                    coordinator,
                    gps_coordinator,
                    vin,
                    vehicle,
                )
            )

    async_add_entities(entities)


class BydPollIntervalNumberMixin:
    """Mixin for hour-based poll interval number entities."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX


class BydRealtimePollIntervalNumber(BydVehicleEntity, BydPollIntervalNumberMixin, NumberEntity):
    """Runtime-configurable realtime polling interval (hours).

    The interval is an entry-level setting: changing it on any vehicle's
    entity applies to every vehicle in the account (persisted in entry options).
    """

    _attr_translation_key = "realtime_poll_interval"
    _attr_native_min_value = MIN_POLL_INTERVAL / 3600
    _attr_native_max_value = MAX_POLL_INTERVAL / 3600
    _attr_native_step = 0.5

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_number_realtime_poll_interval"
        super().__init__(coordinator)

    @property
    def native_value(self) -> float:
        """Return poll interval in hours."""
        return _sec_to_hours(self.coordinator.poll_interval_seconds)

    async def async_set_native_value(self, value: float) -> None:
        """Set and persist poll interval."""
        interval = _hours_to_sec(value)
        interval = max(MIN_POLL_INTERVAL, min(MAX_POLL_INTERVAL, interval))

        # Entry-level setting: apply to every vehicle in this account.
        entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
        for coordinator in entry_data["coordinators"].values():
            coordinator.set_poll_interval(interval)

        options = {**self._entry.options, CONF_POLL_INTERVAL: interval}
        if options != self._entry.options:
            self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()


class BydGpsPollIntervalNumber(BydVehicleEntity, BydPollIntervalNumberMixin, NumberEntity):
    """Runtime-configurable GPS polling interval (hours).

    The interval is an entry-level setting: changing it on any vehicle's
    entity applies to every vehicle in the account (persisted in entry options).
    """

    _attr_translation_key = "gps_poll_interval"
    _attr_native_min_value = MIN_GPS_POLL_INTERVAL / 3600
    _attr_native_max_value = MAX_GPS_POLL_INTERVAL / 3600
    _attr_native_step = 0.5

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: BydDataUpdateCoordinator,
        gps_coordinator: BydGpsUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._gps_coordinator = gps_coordinator
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_number_gps_poll_interval"
        super().__init__(coordinator)

    @property
    def native_value(self) -> float:
        """Return GPS poll interval in hours."""
        return _sec_to_hours(self._gps_coordinator.poll_interval_seconds)

    async def async_set_native_value(self, value: float) -> None:
        """Set and persist GPS poll interval."""
        interval = _hours_to_sec(value)
        interval = max(MIN_GPS_POLL_INTERVAL, min(MAX_GPS_POLL_INTERVAL, interval))

        # Entry-level setting: apply to every vehicle in this account.
        entry_data = self.hass.data[DOMAIN][self._entry.entry_id]
        for gps_coordinator in entry_data["gps_coordinators"].values():
            gps_coordinator.set_poll_interval(interval)

        options = {**self._entry.options, CONF_GPS_POLL_INTERVAL: interval}
        if options != self._entry.options:
            self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()


class BydAcTemperatureNumber(BydVehicleEntity, NumberEntity):
    """Runtime-configurable default A/C temperature.

    This is the temperature applied whenever the A/C is turned on *without* an
    explicitly specified temperature (e.g. via ``climate.turn_on`` or the
    ``OPENAIR`` button).  The value is persisted per-vehicle in the entry
    options so it survives restarts.
    """

    _attr_translation_key = "ac_temperature"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = AC_TEMP_MIN
    _attr_native_max_value = AC_TEMP_MAX
    _attr_native_step = AC_TEMP_STEP
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_number_ac_temperature"
        super().__init__(coordinator)

    @property
    def native_value(self) -> float:
        """Return the persisted default A/C temperature for this vehicle."""
        temps = self._entry.options.get(CONF_AC_TEMPERATURE, {})
        if isinstance(temps, dict):
            value = temps.get(self._vin)
        else:
            value = temps
        try:
            return float(value)
        except (TypeError, ValueError):
            return DEFAULT_AC_TEMPERATURE

    async def async_set_native_value(self, value: float) -> None:
        """Set and persist the default A/C temperature for this vehicle."""
        value = max(AC_TEMP_MIN, min(AC_TEMP_MAX, float(value)))

        temps = dict(self._entry.options.get(CONF_AC_TEMPERATURE, {}))
        if not isinstance(temps, dict):
            temps = {}
        temps[self._vin] = value

        options = {**self._entry.options, CONF_AC_TEMPERATURE: temps}
        if options != self._entry.options:
            self.hass.config_entries.async_update_entry(self._entry, options=options)
        self.async_write_ha_state()
