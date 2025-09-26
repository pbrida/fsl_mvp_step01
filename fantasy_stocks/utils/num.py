from typing import Optional

def to_float(value: Optional[float], default: float = 0.0) -> float:
    """Convert Optional[float] to float safely."""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default
