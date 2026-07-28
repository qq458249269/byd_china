"""Internal constants shared across the library."""

USER_AGENT = "okhttp/4.12.0"
SESSION_EXPIRED_CODES: frozenset[str] = frozenset({"1002", "1005", "1010"})

# ------------------------------------------------------------------
# BYD climate temperature scale  (°C → scale 1-17)
# ------------------------------------------------------------------

_SCALE_MIN = 1
_SCALE_MAX = 17
_OFFSET_C = 14.0
_TEMP_MIN_C = _OFFSET_C + _SCALE_MIN  # 15.0
_TEMP_MAX_C = _OFFSET_C + _SCALE_MAX  # 31.0


def celsius_to_scale(temp_c: float) -> int:
    """Convert a °C temperature (15-31) to BYD's climate scale (1-17).

    Raises :class:`ValueError` if *temp_c* is outside the supported range.
    """
    value = float(temp_c)
    if not _TEMP_MIN_C <= value <= _TEMP_MAX_C:
        raise ValueError(f"temperature must be between {_TEMP_MIN_C} and {_TEMP_MAX_C} °C, got {value}")
    return max(_SCALE_MIN, min(_SCALE_MAX, int(round(value - _OFFSET_C))))


# ------------------------------------------------------------------
# BYD climate duration codes  (minutes → time_span 1-5)
# ------------------------------------------------------------------

_DURATION_TO_CODE: dict[int, int] = {10: 1, 15: 2, 20: 3, 25: 4, 30: 5}
VALID_CLIMATE_DURATIONS: tuple[int, ...] = (10, 15, 20, 25, 30)


def minutes_to_time_span(minutes: int) -> int:
    """Convert a climate duration in minutes to a BYD ``time_span`` code.

    Supported values: 10, 15, 20, 25, 30 → codes 1-5.

    Raises :class:`ValueError` for unsupported durations.
    """
    code = _DURATION_TO_CODE.get(minutes)
    if code is None:
        raise ValueError(f"duration must be one of {VALID_CLIMATE_DURATIONS} minutes, got {minutes}")
    return code
