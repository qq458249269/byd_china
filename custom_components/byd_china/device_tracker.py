"""Device tracker for BYD Vehicle."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydGpsUpdateCoordinator, gcj02_to_wgs84
from .entity import BydVehicleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data.get("coordinators", {})
    gps_coordinators = data.get("gps_coordinators", {})

    entities: list[TrackerEntity] = []
    for vin, coordinator in coordinators.items():
        gps_coordinator = gps_coordinators.get(vin)
        if gps_coordinator is not None:
            vehicle = coordinator.vehicle
            entities.append(BydDeviceTracker(gps_coordinator, vin, vehicle))

    async_add_entities(entities)


class BydDeviceTracker(BydVehicleEntity, TrackerEntity):
    """BYD vehicle device tracker using WGS-84 coordinates.

    The BYD API returns GCJ-02 (国测局坐标), which has a deliberate
    offset for China. We convert to WGS-84 so the HA map shows the
    correct position without offset.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "location"

    def __init__(
        self,
        gps_coordinator: BydGpsUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_device_tracker_location"
        super().__init__(gps_coordinator)

    @property
    def latitude(self) -> float | None:
        gps = self.coordinator.data
        if gps is None:
            return None
        lat = getattr(gps, "latitude", None)
        lon = getattr(gps, "longitude", None)
        if lat is not None and lon is not None:
            wgs84_lat, _ = gcj02_to_wgs84(lat, lon)
            return wgs84_lat
        return None

    @property
    def longitude(self) -> float | None:
        gps = self.coordinator.data
        if gps is None:
            return None
        lat = getattr(gps, "latitude", None)
        lon = getattr(gps, "longitude", None)
        if lat is not None and lon is not None:
            _, wgs84_lon = gcj02_to_wgs84(lat, lon)
            return wgs84_lon
        return None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS
