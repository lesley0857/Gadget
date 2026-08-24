# solar/services/engineering.py

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .constants import (
    SYSTEM_VOLTAGE_CLASSES,
    BATTERY_LEAD_ACID,
    BATTERY_LITHIUM,
    DECIMAL_PLACES,
)
from .exceptions import InvalidDesignInput


# ================================================================
# DECIMAL CONVERSION
# ================================================================

def to_decimal(value, default=None):
    """
    Convert values safely to Decimal.

    Floats are converted through str() to avoid binary float errors.
    """

    if value is None:
        if default is not None:
            return Decimal(str(default))
        raise InvalidDesignInput("A required numeric value is missing.")

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        if default is not None:
            return Decimal(str(default))

        raise InvalidDesignInput(
            f"Invalid numeric value: {value}"
        )


# ================================================================
# ROUNDING
# ================================================================

def round_decimal(value, places=DECIMAL_PLACES):
    value = to_decimal(value)

    return value.quantize(
        places,
        rounding=ROUND_HALF_UP,
    )


# ================================================================
# PERCENTAGE NORMALIZATION
# ================================================================

def normalize_ratio(value):
    """
    Accept either:

        0.95
        95

    and normalize to:

        Decimal("0.95")
    """

    value = to_decimal(value)

    if value > Decimal("1"):
        value = value / Decimal("100")

    if value < Decimal("0"):
        raise InvalidDesignInput(
            "Ratios cannot be negative."
        )

    return value


# ================================================================
# SYSTEM VOLTAGE CLASS
# ================================================================

def get_voltage_class(actual_voltage):
    """
    Map actual equipment voltage to the nearest standard
    system voltage class.

    Examples:

        12.8  -> 12
        25.6  -> 24
        51.2  -> 48
        102.4 -> 96
        204.8 -> 192
    """

    actual_voltage = to_decimal(actual_voltage)

    return min(
        SYSTEM_VOLTAGE_CLASSES,
        key=lambda voltage: abs(voltage - actual_voltage),
    )


# ================================================================
# VALIDATE SYSTEM VOLTAGE
# ================================================================

def validate_system_voltage(system_voltage):
    system_voltage = to_decimal(system_voltage)

    if system_voltage <= 0:
        raise InvalidDesignInput(
            "System voltage must be greater than zero."
        )

    return system_voltage


# ================================================================
# CEILING DIVISION
# ================================================================

def ceil_division(numerator, denominator):
    """
    Decimal-safe ceiling division.
    """

    numerator = to_decimal(numerator)
    denominator = to_decimal(denominator)

    if denominator <= 0:
        raise InvalidDesignInput(
            "Division denominator must be greater than zero."
        )

    quotient = numerator / denominator

    return int(quotient.to_integral_value(rounding="ROUND_CEILING"))


# ================================================================
# BATTERY TYPE NORMALIZATION
# ================================================================

def normalize_battery_type(value):
    if not value:
        return None

    value = str(value).strip().lower()

    aliases = {
        "lead": BATTERY_LEAD_ACID,
        "leadacid": BATTERY_LEAD_ACID,
        "lead_acid": BATTERY_LEAD_ACID,
        "lithium": BATTERY_LITHIUM,
        "li": BATTERY_LITHIUM,
    }

    if value not in aliases:
        raise InvalidDesignInput(
            f"Unsupported battery type: {value}"
        )

    return aliases[value]


# ================================================================
# ENGINE RESULT
# ================================================================

def build_result(
    *,
    status="ok",
    inputs=None,
    calculations=None,
    selected=None,
    candidates=None,
    warnings=None,
    messages=None,
):
    """
    Standard result structure used by every engine.
    """

    return {
        "status": status,
        "inputs": inputs or {},
        "calculations": calculations or {},
        "selected": selected or {},
        "candidates": candidates or [],
        "warnings": warnings or [],
        "messages": messages or [],
    }


# ================================================================
# JSON SAFE
# ================================================================

def make_json_safe(value):
    """
    Convert Decimals recursively into strings for JSONField/session use.
    """

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            key: make_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_safe(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value