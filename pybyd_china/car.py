"""Per-vehicle aggregate — ``BydCar``.

``BydCar`` is the primary domain object for interacting with a single
BYD vehicle.  It wraps the low-level :class:`BydClient` API methods
behind typed capability namespaces and manages vehicle state through
an internal :class:`VehicleStateEngine`.

Usage::

    car = await client.get_car(vin)

    await car.lock.lock()
    await car.hvac.start(temperature=21, duration=20)
    await car.seat.heat(SeatPosition.DRIVER, SeatLevel.HIGH)
    await car.steering.heat(on=True)
    await car.battery.heat(on=True)
    await car.finder.find()
    await car.windows.close()

    state = car.state  # immutable VehicleSnapshot
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from ._capabilities.battery_heat import BatteryHeatCapability
from ._capabilities.finder import FinderCapability
from ._capabilities.hvac import HvacCapability
from ._capabilities.lock import LockCapability
from ._capabilities.seat import SeatCapability
from ._capabilities.steering import SteeringCapability
from ._capabilities.windows import WindowsCapability
from ._state_engine import ProjectionSpec, VehicleSnapshot, VehicleStateEngine
from .exceptions import BydRemoteControlError
from .models.charging import ChargingStatus
from .models.energy import EnergyConsumption
from .models.gps import GpsInfo
from .models.hvac import HvacStatus
from .models.latest_config import VehicleCapabilities
from .models.realtime import VehicleRealtimeData
from .models.vehicle import Vehicle

if TYPE_CHECKING:
    from .client import BydClient

_logger = logging.getLogger(__name__)

_DEFAULT_PROJECTION_TTL: float = 30.0


class BydCar:
    """Per-vehicle aggregate providing typed capability namespaces.

    Holds an internal :class:`VehicleStateEngine` that manages
    immutable :class:`VehicleSnapshot` instances with command
    projections, guard windows, and value-quality validators.

    Parameters
    ----------
    client
        The authenticated :class:`BydClient` instance.
    vin
        Vehicle identification number.
    vehicle
        Vehicle metadata model.
    on_state_changed
        Optional callback fired on every accepted state mutation.
    projection_ttl
        Default TTL for command projections (seconds).
    """

    def __init__(
        self,
        client: BydClient,
        vin: str,
        vehicle: Vehicle,
        *,
        capabilities: VehicleCapabilities | None = None,
        on_state_changed: Callable[[str, VehicleSnapshot], None] | None = None,
        projection_ttl: float = _DEFAULT_PROJECTION_TTL,
    ) -> None:
        self._client = client
        self._vin = vin

        self._engine = VehicleStateEngine(
            vin,
            vehicle,
            on_state_changed=on_state_changed,
            projection_ttl=projection_ttl,
        )
        self._capabilities = capabilities or VehicleCapabilities.model_validate(
            {
                "vin": vin,
                "source": "implicit_default",
                "lock": True,
                "unlock": True,
                "climate": True,
                "car_on": True,
                "battery_heat": True,
                "steering_wheel_heat": True,
                "driver_seat_heat": True,
                "driver_seat_ventilation": True,
                "passenger_seat_heat": True,
                "passenger_seat_ventilation": True,
                "find_car": True,
                "flash_lights": True,
                "close_windows": True,
                "location": True,
            }
        )

        # --- Capability namespaces ---
        self.lock = LockCapability(
            lock_fn=client.lock,
            unlock_fn=client.unlock,
            vin=vin,
            execute_command=self._execute_command,
            available=self._capabilities.lock,
        )
        self.hvac = HvacCapability(
            start_fn=client.start_climate,
            stop_fn=client.stop_climate,
            schedule_fn=client.schedule_climate,
            vin=vin,
            execute_command=self._execute_command,
            available=self._capabilities.climate,
        )
        self.seat = SeatCapability(
            set_seat_climate_fn=client.set_seat_climate,
            vin=vin,
            get_state=lambda: self._engine.snapshot,
            execute_command=self._execute_command,
            driver_heat_available=self._capabilities.driver_seat_heat,
            driver_ventilation_available=self._capabilities.driver_seat_ventilation,
            passenger_heat_available=self._capabilities.passenger_seat_heat,
            passenger_ventilation_available=self._capabilities.passenger_seat_ventilation,
        )
        self.steering = SteeringCapability(
            set_seat_climate_fn=client.set_seat_climate,
            vin=vin,
            get_state=lambda: self._engine.snapshot,
            execute_command=self._execute_command,
            available=self._capabilities.steering_wheel_heat,
        )
        self.battery = BatteryHeatCapability(
            set_battery_heat_fn=client.set_battery_heat,
            vin=vin,
            execute_command=self._execute_command,
            available=self._capabilities.battery_heat,
        )
        self.finder = FinderCapability(
            find_fn=client.find_car,
            flash_fn=client.flash_lights,
            vin=vin,
            execute_command=self._execute_command,
            find_available=self._capabilities.find_car,
            flash_available=self._capabilities.flash_lights,
        )
        self.windows = WindowsCapability(
            close_fn=client.close_windows,
            vin=vin,
            execute_command=self._execute_command,
            close_available=self._capabilities.close_windows,
        )

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def vin(self) -> str:
        """Vehicle identification number."""
        return self._vin

    @property
    def state(self) -> VehicleSnapshot:
        """Current projected vehicle state (immutable snapshot)."""
        return self._engine.snapshot

    @property
    def capabilities(self) -> VehicleCapabilities:
        """Normalized capability availability for this vehicle."""
        return self._capabilities

    # ------------------------------------------------------------------
    # Data fetch methods
    # ------------------------------------------------------------------

    async def update_realtime(self) -> VehicleRealtimeData:
        """Fetch fresh realtime data and merge into state engine."""
        data = await self._client.get_vehicle_realtime(self._vin)
        await self._engine.update_realtime(data)
        return data

    async def update_hvac(self) -> HvacStatus:
        """Fetch fresh HVAC data and merge into state engine."""
        data = await self._client.get_hvac_status(self._vin)
        await self._engine.update_hvac(data)
        return data

    async def update_gps(self) -> GpsInfo:
        """Fetch fresh GPS data and merge into state engine."""
        data = await self._client.get_gps_info(self._vin)
        await self._engine.update_gps(data)
        return data

    async def update_charging(self) -> ChargingStatus:
        """Fetch fresh charging data and merge into state engine."""
        data = await self._client.get_charging_status(self._vin)
        await self._engine.update_charging(data)
        return data

    async def update_energy(self) -> EnergyConsumption:
        """Fetch fresh energy consumption data and merge into state engine."""
        data = await self._client.get_energy_consumption(self._vin)
        await self._engine.update_energy(data)
        return data

    # ------------------------------------------------------------------
    # MQTT integration
    # ------------------------------------------------------------------

    def handle_mqtt_realtime(self, data: VehicleRealtimeData) -> None:
        """Handle an MQTT ``vehicleInfo`` push for this vehicle.

        Routes the data through the state engine's guard window (same
        path as HTTP poll results).  Called synchronously from the event
        loop; spawns an async task for the engine update.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._async_handle_mqtt(data))

    async def _async_handle_mqtt(self, data: VehicleRealtimeData) -> None:
        """Async handler for MQTT realtime data."""
        try:
            await self._engine.update_realtime(data)
        except Exception:
            _logger.debug("Failed to process MQTT realtime for vin=%s", self._vin, exc_info=True)

    def handle_mqtt_charging(self, data: ChargingStatus) -> None:
        """Handle an MQTT ``smartCharge`` push for this vehicle.

        Parses the payload as :class:`ChargingStatus` and routes it
        through the state engine.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._async_handle_mqtt_charging(data))

    async def _async_handle_mqtt_charging(self, data: ChargingStatus) -> None:
        """Async handler for MQTT charging data."""
        try:
            await self._engine.update_charging(data)
        except Exception:
            _logger.debug("Failed to process MQTT charging for vin=%s", self._vin, exc_info=True)

    def handle_mqtt_energy(self, data: EnergyConsumption) -> None:
        """Handle an MQTT ``energyConsumption`` push for this vehicle.

        Parses the payload as :class:`EnergyConsumption` and routes it
        through the state engine.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._async_handle_mqtt_energy(data))

    async def _async_handle_mqtt_energy(self, data: EnergyConsumption) -> None:
        """Async handler for MQTT energy consumption data."""
        try:
            await self._engine.update_energy(data)
        except Exception:
            _logger.debug("Failed to process MQTT energy for vin=%s", self._vin, exc_info=True)

    # ------------------------------------------------------------------
    # Command execution
    # ------------------------------------------------------------------

    async def _execute_command(
        self,
        command_fn: Callable[[], Awaitable[Any]],
        projections: list[ProjectionSpec],
    ) -> None:
        """Execute a vehicle command with projection lifecycle management.

        1. Acquire the per-VIN lock (serialises commands)
        2. Register projections (optimistic state update)
        3. Execute the command
        4. On ``BydRemoteControlError`` — treat as tentative success
        5. On other errors — rollback projections and re-raise

        No post-command reconcile poll is performed.  The projections
        provide immediate optimistic state and the next regular poll
        cycle (or MQTT push) will reconcile actual vehicle state.
        """
        async with self._engine.lock:
            command_id = self._engine.register_projections(projections) if projections else ""
            try:
                await command_fn()
            except BydRemoteControlError:
                _logger.debug(
                    "BydRemoteControlError treated as tentative success for vin=%s (cmd=%s)",
                    self._vin,
                    command_id,
                )
            except Exception:
                if command_id:
                    self._engine.rollback_projections(command_id)
                raise

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Clean up resources.

        Called when the car is removed from the client or on shutdown.
        Currently a no-op — retained as a lifecycle hook for future use.
        """
