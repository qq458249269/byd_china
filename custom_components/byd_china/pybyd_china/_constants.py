"""Internal constants shared across the library."""

# ------------------------------------------------------------------
# BYD climate temperature scale  (°C → scale 1-17)
# ------------------------------------------------------------------

_SCALE_MIN = 1
_SCALE_MAX = 17
_OFFSET_C = 16.0
_TEMP_MIN_C = _OFFSET_C + _SCALE_MIN  # 17.0
_TEMP_MAX_C = _OFFSET_C + _SCALE_MAX  # 33.0


def celsius_to_scale(temp_c: float) -> int:
    """Convert a °C temperature (17-33) to BYD's climate scale (1-17).

    Raises :class:`ValueError` if *temp_c* is outside the supported range.
    """
    value = float(temp_c)
    if not _TEMP_MIN_C <= value <= _TEMP_MAX_C:
        raise ValueError(f"temperature must be between {_TEMP_MIN_C} and {_TEMP_MAX_C} °C, got {value}")
    return max(_SCALE_MIN, min(_SCALE_MAX, int(round(value - _OFFSET_C))))


def scale_to_celsius(scale: float) -> float | None:
    """Convert a BYD climate scale value (1-17) to °C (17-33).

    ``main_setting_temp`` from the API is always scale; precise degrees come
    from ``main_setting_temp_new``. Returns None for anything outside 1-17 so
    callers can fall back instead of mis-decoding a raw °C value.
    """
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return None
    if not _SCALE_MIN <= value <= _SCALE_MAX:
        return None
    return value + _OFFSET_C


