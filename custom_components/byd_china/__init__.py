"""BYD China integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .pybyd_china.client import BydClient

from .const import (
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_DEVICE_PROFILE,
    CONF_GPS_POLL_INTERVAL,
    CONF_LANGUAGE,
    CONF_POLL_INTERVAL,
    CONF_TARGET_BRAND,
    DEFAULT_BASE_URL,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_GPS_POLL_INTERVAL,
    DEFAULT_LANGUAGE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TARGET_BRAND,
    DOMAIN,
    MAX_GPS_POLL_INTERVAL,
    MAX_POLL_INTERVAL,
    MIN_GPS_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    PLATFORMS,
)
from .coordinator import BydApi, BydDataUpdateCoordinator, BydGpsUpdateCoordinator
from .device_fingerprint import async_generate_device_profile

_LOGGER = logging.getLogger(__name__)


def _sanitize_interval(value: int, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, parsed))


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to latest schema."""
    _LOGGER.debug(
        "Migrating BYD config entry %s from version %s",
        entry.entry_id,
        entry.version,
    )

    if entry.version > 5:
        _LOGGER.error(
            "Cannot migrate BYD config entry %s from version %s",
            entry.entry_id,
            entry.version,
        )
        return False

    # Migrate to China defaults
    data = dict(entry.data)
    # Only fill in missing values; keep any user-provided overrides.
    data.setdefault(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE)
    data.setdefault(CONF_LANGUAGE, DEFAULT_LANGUAGE)
    data.setdefault(CONF_BASE_URL, DEFAULT_BASE_URL)
    data.setdefault(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND)
    data.setdefault(CONF_CONTROL_PIN, "")

    new_unique_id = entry.unique_id
    username = data.get("username")
    if isinstance(username, str) and username:
        new_unique_id = f"{username}@{DEFAULT_BASE_URL}"

    version = 5
    hass.config_entries.async_update_entry(
        entry,
        data=data,
        unique_id=new_unique_id,
        version=version,
    )

    _LOGGER.debug("Migration of BYD config entry %s complete", entry.entry_id)
    return True


def _apply_poll_intervals_from_options(
    entry: ConfigEntry,
    entry_data: dict[str, Any],
) -> None:
    poll_interval = _sanitize_interval(
        entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        DEFAULT_POLL_INTERVAL,
        MIN_POLL_INTERVAL,
        MAX_POLL_INTERVAL,
    )
    gps_interval = _sanitize_interval(
        entry.options.get(CONF_GPS_POLL_INTERVAL, DEFAULT_GPS_POLL_INTERVAL),
        DEFAULT_GPS_POLL_INTERVAL,
        MIN_GPS_POLL_INTERVAL,
        MAX_GPS_POLL_INTERVAL,
    )

    for coordinator in entry_data.get("coordinators", {}).values():
        coordinator.set_poll_interval(poll_interval)
    for gps_coordinator in entry_data.get("gps_coordinators", {}).values():
        gps_coordinator.set_poll_interval(gps_interval)


async def _async_handle_entry_update(hass: HomeAssistant, entry: ConfigEntry) -> None:
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if entry_data is None:
        return

    previous_options = entry_data.get("options_snapshot", {})
    current_options = dict(entry.options)
    entry_data["options_snapshot"] = current_options

    changed_keys = {
        key
        for key in set(previous_options) | set(current_options)
        if previous_options.get(key) != current_options.get(key)
    }
    poll_keys = {CONF_POLL_INTERVAL, CONF_GPS_POLL_INTERVAL}

    if changed_keys and changed_keys.issubset(poll_keys):
        _apply_poll_intervals_from_options(entry, entry_data)
        return

    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BYD Vehicle (China) from a config entry."""
    _LOGGER.debug("Setting up BYD config entry %s", entry.entry_id)
    hass.data.setdefault(DOMAIN, {})

    # Ensure a device fingerprint exists
    if CONF_DEVICE_PROFILE not in entry.data:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_DEVICE_PROFILE: await async_generate_device_profile(hass),
            },
        )

    session = async_get_clientsession(hass)
    api = BydApi(hass, entry, session)

    poll_interval = _sanitize_interval(
        entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        DEFAULT_POLL_INTERVAL,
        MIN_POLL_INTERVAL,
        MAX_POLL_INTERVAL,
    )
    gps_interval = _sanitize_interval(
        entry.options.get(CONF_GPS_POLL_INTERVAL, DEFAULT_GPS_POLL_INTERVAL),
        DEFAULT_GPS_POLL_INTERVAL,
        MIN_GPS_POLL_INTERVAL,
        MAX_GPS_POLL_INTERVAL,
    )

    async def _fetch_vehicles(client: BydClient) -> list:
        return await client.get_vehicles()

    try:
        vehicles = await api.async_call(_fetch_vehicles)
    except ConfigEntryAuthFailed:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ConfigEntryNotReady(f"Unable to fetch vehicles: {exc}") from exc
    if not vehicles:
        raise ConfigEntryNotReady("No vehicles available for this account")

    _LOGGER.debug(
        "Discovered %s BYD vehicle(s) for entry %s",
        len(vehicles),
        entry.entry_id,
    )

    coordinators: dict[str, BydDataUpdateCoordinator] = {}
    gps_coordinators: dict[str, BydGpsUpdateCoordinator] = {}

    for vehicle in vehicles:
        vin = vehicle.get("vin", "") if isinstance(vehicle, dict) else vehicle.vin
        vehicle_info = vehicle if isinstance(vehicle, dict) else {}

        telemetry_coordinator = BydDataUpdateCoordinator(
            hass,
            api,
            vin,
            vehicle_info,
            poll_interval,
        )
        gps_coordinator = BydGpsUpdateCoordinator(
            hass,
            api,
            vin,
            gps_interval,
            vehicle_info=vehicle_info,
        )
        coordinators[vin] = telemetry_coordinator
        gps_coordinators[vin] = gps_coordinator

    try:
        # Refresh all vehicles concurrently so multi-vehicle setups don't
        # serialize the (up to ~15s each) realtime polling on startup.
        _LOGGER.debug("Running first refresh for BYD telemetry coordinators")
        results = await asyncio.gather(
            *(
                coordinator.async_config_entry_first_refresh()
                for coordinator in coordinators.values()
            ),
            return_exceptions=True,
        )
        _LOGGER.debug("Running first refresh for BYD GPS coordinators")
        results += await asyncio.gather(
            *(
                gps_coordinator.async_config_entry_first_refresh()
                for gps_coordinator in gps_coordinators.values()
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result
    except Exception as exc:  # noqa: BLE001
        raise ConfigEntryNotReady from exc

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
        "gps_coordinators": gps_coordinators,
        "options_snapshot": dict(entry.options),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_handle_entry_update))
    _LOGGER.debug("BYD config entry %s setup complete", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading BYD config entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if entry_data and "api" in entry_data:
            await entry_data["api"].async_shutdown()
        _LOGGER.debug("Unloaded BYD config entry %s", entry.entry_id)
        if not hass.data.get(DOMAIN):
            _async_unregister_services(hass)
    else:
        _LOGGER.debug("BYD config entry %s unload returned False", entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.debug("Reloading BYD config entry %s", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


# ------------------------------------------------------------------
# Service helpers
# ------------------------------------------------------------------

_SERVICE_FETCH_REALTIME = "fetch_realtime"
_SERVICE_FETCH_GPS = "fetch_gps"

_ALL_SERVICES = (
    _SERVICE_FETCH_REALTIME,
    _SERVICE_FETCH_GPS,
)


def _resolve_vins_from_call(
    hass: HomeAssistant,
    call: ServiceCall,
) -> list[tuple[str, str]]:
    device_ids: list[str] = call.data.get("device_id", [])
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    dev_reg = dr.async_get(hass)
    results: list[tuple[str, str]] = []

    for device_id in device_ids:
        device = dev_reg.async_get(device_id)
        if device is None:
            continue
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                vin = identifier[1]
                for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
                    coordinators = entry_data.get("coordinators", {})
                    if vin in coordinators:
                        results.append((entry_id, vin))
                        break

    if not results:
        raise HomeAssistantError("No BYD vehicle devices found for the given targets")
    return results


def _get_coordinators(
    hass: HomeAssistant,
    entry_id: str,
    vin: str,
) -> tuple[BydDataUpdateCoordinator, BydGpsUpdateCoordinator | None]:
    entry_data: dict[str, Any] = hass.data[DOMAIN][entry_id]
    telemetry: BydDataUpdateCoordinator = entry_data["coordinators"][vin]
    gps: BydGpsUpdateCoordinator | None = entry_data.get("gps_coordinators", {}).get(
        vin
    )
    return telemetry, gps


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, _SERVICE_FETCH_REALTIME):
        return

    async def _handle_fetch_realtime(call: ServiceCall) -> None:
        for entry_id, vin in _resolve_vins_from_call(hass, call):
            coordinator, _ = _get_coordinators(hass, entry_id, vin)
            await coordinator.async_force_refresh()

    async def _handle_fetch_gps(call: ServiceCall) -> None:
        for entry_id, vin in _resolve_vins_from_call(hass, call):
            _, gps = _get_coordinators(hass, entry_id, vin)
            if gps is not None:
                await gps.async_force_refresh()

    hass.services.async_register(
        DOMAIN, _SERVICE_FETCH_REALTIME, _handle_fetch_realtime
    )
    hass.services.async_register(DOMAIN, _SERVICE_FETCH_GPS, _handle_fetch_gps)

    _LOGGER.debug("Registered %s domain services", len(_ALL_SERVICES))


def _async_unregister_services(hass: HomeAssistant) -> None:
    for service in _ALL_SERVICES:
        hass.services.async_remove(DOMAIN, service)
    _LOGGER.debug("Unregistered %s domain services", len(_ALL_SERVICES))
