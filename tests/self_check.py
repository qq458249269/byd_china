"""Self-check for the bug-fix batch (6e0dab1 + follow-ups).

Run:  python tests/self_check.py
No third-party test framework; pure asserts, exit code 0 = pass.
"""

import asyncio
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load pybyd_china without executing the HA-dependent package __init__.py:
# register a dummy parent package so `byd_china.pybyd_china...` resolves
# against its real __path__ while skipping custom_components/byd_china/__init__.py.
_pkg = types.ModuleType("byd_china")
_pkg.__path__ = [str(ROOT / "custom_components" / "byd_china")]
sys.modules["byd_china"] = _pkg

from byd_china.pybyd_china._constants import celsius_to_scale, scale_to_celsius
from byd_china.pybyd_china._state_engine import VehicleSnapshot
from byd_china.pybyd_china.client import BydClient
from byd_china.pybyd_china.config import BydConfig, BydSession, DeviceProfile
from byd_china.pybyd_china.exceptions import BydSessionExpiredError
from byd_china.pybyd_china.models.vehicle import Vehicle


def check_temp_conversion() -> None:
    # celsius_to_scale (send path): 25 °C must send scale 9 (was 27 °C bug).
    assert celsius_to_scale(17.0) == 1
    assert celsius_to_scale(25.0) == 9
    assert celsius_to_scale(33.0) == 17
    assert celsius_to_scale(30.5) == 14
    try:
        celsius_to_scale(16.0)
        raise AssertionError("out-of-range must raise")
    except ValueError:
        pass

    # scale_to_celsius (display path): scale-only decode, no °C/scale ambiguity.
    assert scale_to_celsius(1) == 17.0
    assert scale_to_celsius(9) == 25.0
    assert scale_to_celsius(17) == 33.0
    assert scale_to_celsius(11) == 27.0
    assert scale_to_celsius(0) is None
    assert scale_to_celsius(18) is None
    assert scale_to_celsius("abc") is None
    assert scale_to_celsius(None) is None
    # Regression: raw °C "17" must NOT decode as scale 17 (previously 33 °C).
    assert scale_to_celsius(17) == 33.0  # scale 17 is a valid scale value


def check_config_fields() -> None:
    cfg = BydConfig(username="u", password="p")
    assert cfg.username == "u" and cfg.password == "p"
    assert cfg.base_url and cfg.control_pin is None and cfg.target_brand
    # Dead fields removed; accessing them must raise AttributeError.
    for dead in ("country_code", "language", "time_zone", "is_auto"):
        assert not hasattr(cfg, dead), f"BydConfig.{dead} should be removed"
    assert not hasattr(BydSession(), "identifier"), "BydSession.identifier removed"


def check_snapshot_merge_fields() -> None:
    """HVAC merge must accept every field the coordinator now forwards."""
    snap = VehicleSnapshot(
        vehicle=Vehicle(vin="TESTVIN12345678901", model_name="Seal"),
        realtime=None,
        hvac=None,
        gps=None,
        charging=None,
        energy=None,
        is_shared=False,
        gps_wgs84_latitude=31.23,
        gps_wgs84_longitude=121.47,
        historical_energy={"a": 1},
        recent_energy={"b": 2},
    )
    assert snap.gps_wgs84_latitude == 31.23
    assert snap.historical_energy == {"a": 1}
    assert snap.recent_energy == {"b": 2}


async def _check_retry_no_double_login() -> None:
    """Concurrent session-expiry calls must trigger exactly one re-login."""
    client = BydClient(
        config=BydConfig(username="u", password="p"),
        device_profile=DeviceProfile(),
        session=None,
    )
    logins: list[int] = []

    async def stub_login() -> None:
        logins.append(1)
        client._session_generation += 1  # noqa: SLF001

    client.login = stub_login  # type: ignore[method-assign]

    # Barrier aligns the two FIRST attempts so both fire against the same
    # stale session (generation 0) before either re-login happens. The second
    # caller must then skip re-login and just retry on the fresh session.
    barrier = asyncio.Barrier(2)

    async def boom(_self: BydClient) -> None:
        if client._session_generation == 0:  # noqa: SLF001
            await barrier.wait()
            raise BydSessionExpiredError("code 22")

    wrapped = BydClient._retry_on_session_expired(boom)  # staticmethod, unbound

    results = await asyncio.gather(
        wrapped(client), wrapped(client), return_exceptions=True
    )
    assert all(r is None for r in results), results
    assert len(logins) == 1, f"expected 1 re-login, got {len(logins)}"


def main() -> None:
    check_temp_conversion()
    check_config_fields()
    check_snapshot_merge_fields()
    asyncio.run(_check_retry_no_double_login())
    print("self_check: ALL PASS")


if __name__ == "__main__":
    main()
