"""Internal constants shared across the library."""

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


