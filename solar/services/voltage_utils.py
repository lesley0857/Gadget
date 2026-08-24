"""
solar/services/voltage_utils.py

Shared voltage utilities used by the solar engineering engines.

This module contains electrical-voltage relationships only.
It does not select products.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict


def to_decimal(
    value: Any,
    default: Decimal = Decimal("0"),
) -> Decimal:
    """
    Safely convert a value to Decimal.
    """

    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):
        return default


def battery_series_count(
    system_voltage: Any,
    battery_nominal_voltage: Any,
) -> int:
    """
    Determine the minimum number of identical batteries
    required in series to reach or exceed the nominal system
    voltage.

    Example:

        48 V system
        12.8 V battery

        ceil(48 / 12.8) = 4
    """

    system = to_decimal(
        system_voltage
    )

    battery = to_decimal(
        battery_nominal_voltage
    )

    if system <= 0:
        raise ValueError(
            "System voltage must be greater than zero."
        )

    if battery <= 0:
        raise ValueError(
            "Battery nominal voltage must be greater than zero."
        )

    return int(
        (
            system / battery
        ).to_integral_value(
            rounding="ROUND_CEILING"
        )
    )


def battery_bank_voltage(
    battery_nominal_voltage: Any,
    series_count: Any,
) -> Decimal:
    """
    Calculate actual nominal bank voltage.
    """

    battery = to_decimal(
        battery_nominal_voltage
    )

    series = int(
        to_decimal(
            series_count
        )
    )

    if battery <= 0:
        raise ValueError(
            "Battery nominal voltage must be greater than zero."
        )

    if series < 1:
        raise ValueError(
            "Series count must be at least one."
        )

    return (
        battery
        * Decimal(series)
    )


def battery_parallel_count(
    required_bank_capacity_ah: Any,
    battery_capacity_ah: Any,
) -> int:
    """
    Determine the number of parallel battery strings required
    to satisfy the required Ah capacity.

    This is capacity sizing only.

    Voltage remains determined by the series count.
    """

    required = to_decimal(
        required_bank_capacity_ah
    )

    battery_capacity = to_decimal(
        battery_capacity_ah
    )

    if required <= 0:
        return 0

    if battery_capacity <= 0:
        raise ValueError(
            "Battery capacity must be greater than zero."
        )

    return int(
        (
            required / battery_capacity
        ).to_integral_value(
            rounding="ROUND_CEILING"
        )
    )


def battery_bank_configuration(
    system_voltage: Any,
    battery_nominal_voltage: Any,
    required_capacity_ah: Any,
    battery_capacity_ah: Any,
) -> Dict[str, Any]:
    """
    Produce the complete basic series/parallel configuration
    relationship.

    Example:

        System voltage: 48 V
        Battery: 12.8 V / 200 Ah
        Required capacity: 400 Ah

        Series:
            4

        Parallel:
            2

        Quantity:
            8

        Actual bank voltage:
            51.2 V

        Actual bank capacity:
            400 Ah
    """

    series = battery_series_count(
        system_voltage,
        battery_nominal_voltage,
    )

    parallel = battery_parallel_count(
        required_capacity_ah,
        battery_capacity_ah,
    )

    if parallel < 1:
        parallel = 1

    actual_voltage = battery_bank_voltage(
        battery_nominal_voltage,
        series,
    )

    actual_capacity = (
        to_decimal(
            battery_capacity_ah
        )
        * Decimal(parallel)
    )

    quantity = (
        series
        * parallel
    )

    return {
        "series": series,
        "parallel": parallel,
        "quantity": quantity,
        "actual_bank_voltage": actual_voltage,
        "actual_bank_capacity_ah": (
            actual_capacity
        ),
    }