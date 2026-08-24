"""
solar/services/battery_engine.py

PHASE 3
BATTERY SELECTION + BATTERY BANK ENGINE

Engineering workflow
--------------------

    LOAD ENGINE
         |
         v
    SYSTEM VOLTAGE ENGINE
         |
         v
    BATTERY ENGINE
         |
         +--> Battery energy requirement
         |
         +--> Battery candidate evaluation
         |
         +--> Battery nominal-voltage compatibility
         |
         +--> Series configuration
         |
         +--> Parallel configuration
         |
         +--> Actual bank voltage
         |
         +--> Actual bank capacity
         |
         +--> Usable battery energy
         |
         +--> Discharge-current validation
         |
         +--> Candidate ranking
         |
         v
    PHASE 4 - PV/PANEL ENGINE


IMPORTANT
---------

The following three quantities are deliberately kept separate:

1. SYSTEM VOLTAGE
   The nominal DC system class selected by Phase 2.

2. BATTERY NOMINAL VOLTAGE
   The manufacturer's nominal voltage of ONE battery.

3. BATTERY BANK VOLTAGE
   Battery nominal voltage multiplied by the number of batteries
   connected in series.

Example:

    System voltage = 48 V
    Battery = 12.8 V

    4 batteries in series
        =
    51.2 V actual nominal battery-bank voltage

The system is still a 48 V-class system.

This module does NOT modify database models.

All internal engineering arithmetic uses Decimal.
Database FloatField values are converted safely to Decimal before
calculation.

No template code belongs in this module.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional


# ================================================================
# ENGINE INFORMATION
# ================================================================

ENGINE_NAME = "Battery Selection & Bank Engine"
ENGINE_VERSION = "3.0.0"


# ================================================================
# DECIMAL CONSTANTS
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


# ================================================================
# DEFAULT ENGINEERING VALUES
# ================================================================

DEFAULT_BATTERY_EFFICIENCY = Decimal("0.95")

DEFAULT_LEAD_ACID_DOD = Decimal("0.50")
DEFAULT_LITHIUM_DOD = Decimal("0.95")

DEFAULT_AUTONOMY_DAYS = Decimal("1")
DEFAULT_SYSTEM_RESERVE = Decimal("1.00")

# Maximum recommended continuous battery discharge loading.
#
# This is deliberately conservative because actual battery
# manufacturer discharge limits are checked separately.
DEFAULT_MAX_DISCHARGE_UTILIZATION = Decimal("0.80")

# Battery-voltage matching tolerance.
#
# A battery bank can be above the nominal system class because
# battery technologies commonly use values such as:
#
#   12.8 V
#   25.6 V
#   51.2 V
#
# These are normal for 12/24/48 V-class systems.
#
# Compatibility with a specific inverter is a later-stage
# equipment check.
SYSTEM_VOLTAGE_TOLERANCE_PERCENT = Decimal("15")


# ================================================================
# DEFAULT BATTERY PREFERENCES
# ================================================================

BATTERY_TYPE_PREFERENCE = {
    "lithium": Decimal("1"),
    "lead_acid": Decimal("0.75"),
}


# ================================================================
# SAFE DECIMAL CONVERSION
# ================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert any numeric-like value to Decimal safely.

    Float values are converted through str() to prevent binary
    floating-point artefacts from entering engineering formulas.
    """

    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return default


def non_negative(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert to Decimal and clamp negative values to zero.
    """

    result = to_decimal(
        value,
        default,
    )

    if result < ZERO:
        return ZERO

    return result


def positive_or_default(
    value: Any,
    default: Decimal,
) -> Decimal:
    """
    Return a positive Decimal or the supplied default.
    """

    result = to_decimal(
        value,
        default,
    )

    if result <= ZERO:
        return default

    return result


def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Round Decimal values consistently.
    """

    number = to_decimal(value)

    quantum = Decimal("1").scaleb(-places)

    return number.quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )


def output_number(
    value: Any,
    places: int = 2,
):
    """
    Convert Decimal values to JSON-friendly int/float values.
    """

    number = round_decimal(
        value,
        places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ================================================================
# INTEGER CEILING
# ================================================================

def ceil_decimal(
    value: Decimal,
) -> int:
    """
    Decimal ceiling conversion to integer.
    """

    if value <= ZERO:
        return 0

    return int(
        value.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


# ================================================================
# BATTERY DEFAULTS
# ================================================================

def normalize_depth_of_discharge(
    battery_type: Any,
    value: Any,
) -> Decimal:
    """
    Normalize battery DoD.

    Accepted examples:

        0.5
        0.95
        50
        95

    Battery-model values are expected to be fractions, but the
    engine also accepts percentage input defensively.
    """

    battery_type = str(
        battery_type or ""
    ).strip().lower()

    dod = to_decimal(
        value,
        ZERO,
    )

    if dod > ONE:
        dod = dod / HUNDRED

    if dod <= ZERO:
        if battery_type == "lithium":
            dod = DEFAULT_LITHIUM_DOD
        else:
            dod = DEFAULT_LEAD_ACID_DOD

    # DoD cannot physically exceed 100%.
    if dod > ONE:
        dod = ONE

    return dod


def normalize_efficiency(
    value: Any,
    default: Decimal = DEFAULT_BATTERY_EFFICIENCY,
) -> Decimal:
    """
    Normalize battery efficiency.

    Accepted:

        0.95
        95
    """

    efficiency = to_decimal(
        value,
        default,
    )

    if efficiency <= ZERO:
        return default

    if efficiency > ONE:
        efficiency = efficiency / HUNDRED

    if efficiency <= ZERO:
        return default

    if efficiency > ONE:
        efficiency = ONE

    return efficiency


# ================================================================
# SYSTEM VOLTAGE EXTRACTION
# ================================================================

def extract_system_voltage(
    voltage_result: Dict[str, Any],
) -> Decimal:
    """
    Extract the canonical system voltage from Phase 2.

    Canonical key:

        system_voltage

    Compatibility aliases are accepted only so old saved results
    do not immediately break.
    """

    if not isinstance(
        voltage_result,
        dict,
    ):
        return ZERO

    candidates = (
        voltage_result.get("system_voltage"),
        voltage_result.get(
            "recommended_system_voltage"
        ),
        voltage_result.get(
            "selected_voltage"
        ),
        voltage_result.get(
            "minimum_system_voltage"
        ),
        voltage_result.get(
            "required",
            {},
        ).get(
            "system_voltage"
        )
        if isinstance(
            voltage_result.get(
                "required",
                {},
            ),
            dict,
        )
        else None,
    )

    for candidate in candidates:

        voltage = to_decimal(
            candidate
        )

        if voltage > ZERO:
            return voltage

    return ZERO


# ================================================================
# LOAD ENERGY EXTRACTION
# ================================================================
def extract_daily_energy(
    load_result: Dict[str, Any],
) -> Decimal:
    """
    Extract daily energy from the Phase 1 Load Engine result.

    Phase 1 canonical result locations include:

        calculations.daily_energy_wh
        selected.daily_energy_wh
        load_rows[*].daily_energy_wh

    Compatibility fallbacks are retained for older result
    structures.

    If direct daily energy is unavailable, the engine attempts
    to derive it from:

        load_watts × daily_operating_hours

    This function does not modify the Phase 1 result contract.
    """

    if not isinstance(load_result, dict):
        return ZERO

    # ------------------------------------------------------------
    # 1. CANONICAL PHASE 1 CALCULATIONS
    # ------------------------------------------------------------

    calculations = load_result.get(
        "calculations",
        {},
    )

    if isinstance(calculations, dict):
        for key in (
            "daily_energy_wh",
            "daily_energy",
            "energy_wh_per_day",
            "daily_consumption_wh",
            "daily_load_wh",
        ):
            value = non_negative(
                calculations.get(key)
            )

            if value > ZERO:
                return value

    # ------------------------------------------------------------
    # 2. PHASE 1 SELECTED RESULT
    # ------------------------------------------------------------

    selected = load_result.get(
        "selected",
        {},
    )

    if isinstance(selected, dict):
        for key in (
            "daily_energy_wh",
            "daily_energy",
            "energy_wh_per_day",
            "daily_consumption_wh",
            "daily_load_wh",
        ):
            value = non_negative(
                selected.get(key)
            )

            if value > ZERO:
                return value

    # ------------------------------------------------------------
    # 3. TOP-LEVEL COMPATIBILITY
    # ------------------------------------------------------------

    for key in (
        "daily_energy_wh",
        "daily_energy",
        "energy_wh_per_day",
        "daily_consumption_wh",
        "daily_load_wh",
    ):
        value = non_negative(
            load_result.get(key)
        )

        if value > ZERO:
            return value

    # ------------------------------------------------------------
    # 4. LOAD ROW FALLBACK
    # ------------------------------------------------------------

    load_rows = load_result.get(
        "load_rows",
        [],
    )

    if isinstance(load_rows, list):
        total_daily_energy = ZERO

        for row in load_rows:
            if not isinstance(row, dict):
                continue

            total_daily_energy += non_negative(
                row.get(
                    "daily_energy_wh"
                )
            )

        if total_daily_energy > ZERO:
            return total_daily_energy

    # ------------------------------------------------------------
    # 5. LEGACY DERIVATION
    # ------------------------------------------------------------

    running_load = non_negative(
        load_result.get(
            "load_watts",
            load_result.get(
                "running_load",
                0,
            ),
        )
    )

    daily_hours = non_negative(
        load_result.get(
            "daily_operating_hours",
            load_result.get(
                "operating_hours_per_day",
                load_result.get(
                    "hours_per_day",
                    0,
                ),
            ),
        )
    )

    if (
        running_load > ZERO
        and daily_hours > ZERO
    ):
        return (
            running_load
            * daily_hours
        )

    return ZERO


# ================================================================
# AUTONOMY EXTRACTION
# ================================================================

def extract_autonomy_days(
    load_result: Dict[str, Any],
    autonomy_days: Any = None,
) -> Decimal:
    """
    Determine required battery autonomy.

    Priority:

        explicit function argument
            ↓
        load-result autonomy
            ↓
        one day

    The engine uses days rather than hours as the canonical
    storage-duration unit.
    """

    if autonomy_days is not None:

        result = to_decimal(
            autonomy_days
        )

        if result > ZERO:
            return result

    if isinstance(
        load_result,
        dict,
    ):

        for key in (
            "autonomy_days",
            "backup_days",
            "battery_autonomy_days",
        ):

            result = to_decimal(
                load_result.get(key)
            )

            if result > ZERO:
                return result

    return DEFAULT_AUTONOMY_DAYS


# ================================================================
# REQUIRED ENERGY
# ================================================================

def calculate_required_storage_energy(
    daily_energy_wh: Any,
    autonomy_days: Any = DEFAULT_AUTONOMY_DAYS,
    reserve_factor: Any = DEFAULT_SYSTEM_RESERVE,
) -> Dict[str, Decimal]:
    """
    Calculate required nominal battery storage energy.

    Formula:

        required load energy
            =
        daily energy × autonomy days

    Then account for reserve:

        design energy
            =
        required load energy × reserve factor
    """

    daily_energy = non_negative(
        daily_energy_wh
    )

    days = positive_or_default(
        autonomy_days,
        DEFAULT_AUTONOMY_DAYS,
    )

    reserve = positive_or_default(
        reserve_factor,
        DEFAULT_SYSTEM_RESERVE,
    )

    autonomy_energy = (
        daily_energy
        * days
    )

    design_energy = (
        autonomy_energy
        * reserve
    )

    return {
        "daily_energy_wh": daily_energy,
        "autonomy_days": days,
        "reserve_factor": reserve,
        "autonomy_energy_wh": autonomy_energy,
        "design_energy_wh": design_energy,
    }


# ================================================================
# BATTERY NOMINAL VOLTAGE / SYSTEM CLASS
# ================================================================

def calculate_series_count(
    system_voltage: Any,
    battery_voltage: Any,
) -> int:
    """
    Determine the minimum integer series count required to reach
    the selected system voltage class.

    Examples:

        48 / 12.0  -> 4
        48 / 12.8  -> 4
        48 / 24.0  -> 2
        48 / 25.6  -> 2
        48 / 48.0  -> 1
        48 / 51.2  -> 1
    """

    system = to_decimal(
        system_voltage
    )

    battery = to_decimal(
        battery_voltage
    )

    if system <= ZERO:
        raise ValueError(
            "System voltage must be greater than zero."
        )

    if battery <= ZERO:
        raise ValueError(
            "Battery nominal voltage must be greater than zero."
        )

    return ceil_decimal(
        system / battery
    )


def calculate_bank_voltage(
    battery_voltage: Any,
    series_count: Any,
) -> Decimal:
    """
    Calculate actual nominal battery-bank voltage.
    """

    voltage = to_decimal(
        battery_voltage
    )

    series = int(
        to_decimal(
            series_count
        )
    )

    if voltage <= ZERO:
        raise ValueError(
            "Battery voltage must be greater than zero."
        )

    if series < 1:
        raise ValueError(
            "Series count must be at least one."
        )

    return (
        voltage
        * Decimal(series)
    )


# ================================================================
# VOLTAGE COMPATIBILITY
# ================================================================

def evaluate_voltage_compatibility(
    system_voltage: Any,
    battery_voltage: Any,
    series_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Evaluate whether an individual battery can form a sensible
    bank for the selected system voltage class.

    This is a system-class compatibility check.

    It is NOT an inverter manufacturer voltage-range check.

    The inverter engine will later perform the exact equipment
    operating-voltage validation.
    """

    system = to_decimal(
        system_voltage
    )

    battery = to_decimal(
        battery_voltage
    )

    if series_count is None:
        try:
            series_count = calculate_series_count(
                system,
                battery,
            )
        except ValueError:
            return {
                "compatible": False,
                "reason": (
                    "Invalid system or battery voltage."
                ),
            }

    actual_bank_voltage = (
        calculate_bank_voltage(
            battery,
            series_count,
        )
    )

    if system <= ZERO:
        return {
            "compatible": False,
            "reason": (
                "System voltage is invalid."
            ),
        }

    voltage_deviation = (
        (
            actual_bank_voltage
            - system
        )
        /
        system
        *
        HUNDRED
    )

    absolute_deviation = abs(
        voltage_deviation
    )

    # A bank that falls below the selected system class is not
    # acceptable.
    if actual_bank_voltage < system:
        return {
            "compatible": False,
            "series_count": series_count,
            "actual_bank_voltage": actual_bank_voltage,
            "voltage_deviation_percent": (
                voltage_deviation
            ),
            "reason": (
                "Battery bank does not reach the selected "
                "system-voltage class."
            ),
        }

    # A large overshoot is flagged. It is not automatically
    # declared impossible because some battery chemistries use
    # nominal voltages such as 51.2 V for 48 V-class systems.
    if (
        absolute_deviation
        > SYSTEM_VOLTAGE_TOLERANCE_PERCENT
    ):
        return {
            "compatible": False,
            "series_count": series_count,
            "actual_bank_voltage": actual_bank_voltage,
            "voltage_deviation_percent": (
                voltage_deviation
            ),
            "reason": (
                "Actual battery-bank nominal voltage differs "
                "too much from the selected system class. "
                "Exact inverter DC voltage compatibility must "
                "also be verified."
            ),
        }

    return {
        "compatible": True,
        "series_count": series_count,
        "actual_bank_voltage": actual_bank_voltage,
        "voltage_deviation_percent": (
            voltage_deviation
        ),
        "reason": (
            "Battery bank is compatible with the selected "
            "system-voltage class subject to equipment "
            "voltage-range verification."
        ),
    }


# ================================================================
# BATTERY CAPACITY
# ================================================================

def calculate_parallel_count(
    required_bank_capacity_ah: Any,
    battery_capacity_ah: Any,
) -> int:
    """
    Calculate the number of parallel strings required.

    Formula:

        parallel strings
            =
        ceil(required Ah / battery Ah)
    """

    required = non_negative(
        required_bank_capacity_ah
    )

    battery_capacity = non_negative(
        battery_capacity_ah
    )

    if required <= ZERO:
        return 1

    if battery_capacity <= ZERO:
        raise ValueError(
            "Battery capacity must be greater than zero."
        )

    return ceil_decimal(
        required
        /
        battery_capacity
    )


# ================================================================
# BATTERY ENERGY MODEL
# ================================================================

def calculate_battery_bank(
    battery_voltage: Any,
    battery_capacity_ah: Any,
    depth_of_discharge: Any,
    efficiency: Any,
    series_count: int,
    parallel_count: int,
) -> Dict[str, Decimal]:
    """
    Calculate complete electrical characteristics of a battery
    bank.

    Nominal energy:

        bank voltage × bank Ah

    Usable energy:

        nominal energy × DoD × efficiency
    """

    voltage = positive_or_default(
        battery_voltage,
        ZERO,
    )

    capacity = positive_or_default(
        battery_capacity_ah,
        ZERO,
    )

    dod = normalize_depth_of_discharge(
        "",
        depth_of_discharge,
    )

    battery_efficiency = normalize_efficiency(
        efficiency
    )

    if voltage <= ZERO:
        raise ValueError(
            "Battery voltage must be greater than zero."
        )

    if capacity <= ZERO:
        raise ValueError(
            "Battery capacity must be greater than zero."
        )

    if series_count < 1:
        raise ValueError(
            "Series count must be at least one."
        )

    if parallel_count < 1:
        raise ValueError(
            "Parallel count must be at least one."
        )

    bank_voltage = (
        voltage
        * Decimal(series_count)
    )

    bank_capacity = (
        capacity
        * Decimal(parallel_count)
    )

    nominal_energy = (
        bank_voltage
        * bank_capacity
    )

    usable_energy = (
        nominal_energy
        * dod
        * battery_efficiency
    )

    return {
        "bank_voltage": bank_voltage,
        "bank_capacity_ah": bank_capacity,
        "nominal_energy_wh": nominal_energy,
        "usable_energy_wh": usable_energy,
        "usable_energy_kwh": (
            usable_energy
            / Decimal("1000")
        ),
        "depth_of_discharge": dod,
        "efficiency": battery_efficiency,
    }


# ================================================================
# CURRENT CAPABILITY
# ================================================================

def calculate_required_battery_current(
    power_watts: Any,
    bank_voltage: Any,
    inverter_efficiency: Any = Decimal("0.95"),
) -> Decimal:
    """
    Estimate battery-side current required by the inverter.

        I = P / (V × inverter efficiency)
    """

    power = non_negative(
        power_watts
    )

    voltage = positive_or_default(
        bank_voltage,
        ZERO,
    )

    efficiency = normalize_efficiency(
        inverter_efficiency,
        Decimal("0.95"),
    )

    if (
        power <= ZERO
        or voltage <= ZERO
    ):
        return ZERO

    return (
        power
        /
        (
            voltage
            * efficiency
        )
    )


def calculate_bank_discharge_capability(
    battery_max_discharge_current: Any,
    parallel_count: int,
) -> Decimal:
    """
    Calculate the theoretical continuous discharge capability
    of parallel battery strings.

    Series connection does NOT multiply current capability.

    Parallel connection DOES multiply current capability.

        bank current capability
            =
        battery current capability × parallel strings
    """

    battery_current = non_negative(
        battery_max_discharge_current
    )

    if parallel_count < 1:
        return ZERO

    return (
        battery_current
        * Decimal(parallel_count)
    )


def evaluate_discharge_capability(
    required_current: Any,
    available_current: Any,
    utilization: Any = DEFAULT_MAX_DISCHARGE_UTILIZATION,
) -> Dict[str, Any]:
    """
    Evaluate whether the battery bank has adequate continuous
    discharge-current capability.

    A utilization factor is applied so the battery is not designed
    permanently at its absolute maximum discharge rating.
    """

    required = non_negative(
        required_current
    )

    available = non_negative(
        available_current
    )

    utilization_factor = to_decimal(
        utilization,
        DEFAULT_MAX_DISCHARGE_UTILIZATION,
    )

    if (
        utilization_factor <= ZERO
        or utilization_factor > ONE
    ):
        utilization_factor = (
            DEFAULT_MAX_DISCHARGE_UTILIZATION
        )

    design_available = (
        available
        * utilization_factor
    )

    if required <= design_available:
        return {
            "pass": True,
            "required_current": required,
            "available_current": available,
            "design_available_current": (
                design_available
            ),
            "utilization": utilization_factor,
            "margin_current": (
                design_available
                - required
            ),
            "reason": (
                "Battery bank has adequate continuous "
                "discharge-current capability."
            ),
        }

    return {
        "pass": False,
        "required_current": required,
        "available_current": available,
        "design_available_current": (
            design_available
        ),
        "utilization": utilization_factor,
        "margin_current": (
            design_available
            - required
        ),
        "reason": (
            "Battery bank discharge-current capability "
            "is insufficient for the estimated continuous "
            "load."
        ),
    }


# ================================================================
# BATTERY RECORD NORMALIZATION
# ================================================================

def normalize_battery_record(
    battery: Any,
) -> Dict[str, Any]:
    """
    Convert a Django Battery object OR dictionary into one
    consistent internal representation.

    This is one of the main safeguards against datatype mismatch.
    """

    if isinstance(
        battery,
        dict,
    ):

        getter = battery.get

        battery_id = getter(
            "id"
        )

        brand = getter(
            "brand",
            "",
        )

        model = getter(
            "model",
            "",
        )

        name = getter(
            "name",
            model,
        )

        battery_type = getter(
            "battery_type",
            "",
        )

        voltage = getter(
            "voltage",
            0,
        )

        capacity_ah = getter(
            "capacity_ah",
            0,
        )

        dod = getter(
            "depth_of_discharge",
            None,
        )

        efficiency = getter(
            "efficiency",
            DEFAULT_BATTERY_EFFICIENCY,
        )

        max_discharge_current = getter(
            "max_discharge_current",
            0,
        )

        max_charge_current = getter(
            "max_charge_current",
            0,
        )

        warranty_years = getter(
            "warranty_years",
            0,
        )

        weight = getter(
            "weight",
            0,
        )

        cycles = getter(
            "cycles",
            0,
        )

        price = getter(
            "price",
            0,
        )

        active = getter(
            "active",
            True,
        )

    else:

        battery_id = getattr(
            battery,
            "id",
            None,
        )

        brand = getattr(
            battery,
            "brand",
            "",
        )

        model = getattr(
            battery,
            "model",
            "",
        )

        name = getattr(
            battery,
            "name",
            model,
        )

        battery_type = getattr(
            battery,
            "battery_type",
            "",
        )

        voltage = getattr(
            battery,
            "voltage",
            0,
        )

        capacity_ah = getattr(
            battery,
            "capacity_ah",
            0,
        )

        dod = getattr(
            battery,
            "depth_of_discharge",
            None,
        )

        efficiency = getattr(
            battery,
            "efficiency",
            DEFAULT_BATTERY_EFFICIENCY,
        )

        max_discharge_current = getattr(
            battery,
            "max_discharge_current",
            0,
        )

        max_charge_current = getattr(
            battery,
            "max_charge_current",
            0,
        )

        warranty_years = getattr(
            battery,
            "warranty_years",
            0,
        )

        weight = getattr(
            battery,
            "weight",
            0,
        )

        cycles = getattr(
            battery,
            "cycles",
            0,
        )

        price = getattr(
            battery,
            "price",
            0,
        )

        active = getattr(
            battery,
            "active",
            True,
        )

    normalized_type = str(
        battery_type or ""
    ).strip().lower()

    normalized_dod = normalize_depth_of_discharge(
        normalized_type,
        dod,
    )

    normalized_efficiency = normalize_efficiency(
        efficiency
    )

    return {
        "id": battery_id,
        "brand": str(
            brand or ""
        ),
        "model": str(
            model or ""
        ),
        "name": str(name or model or ""),
        "battery_type": normalized_type,
        "voltage": to_decimal(
            voltage
        ),
        "capacity_ah": to_decimal(
            capacity_ah
        ),
        "depth_of_discharge": normalized_dod,
        "efficiency": normalized_efficiency,
        "max_discharge_current": to_decimal(
            max_discharge_current
        ),
        "max_charge_current": to_decimal(
            max_charge_current
        ),
        "warranty_years": int(
            to_decimal(
                warranty_years
            )
        ),
        "weight": to_decimal(
            weight
        ),
        "cycles": int(
            to_decimal(
                cycles
            )
        ),
        "price": to_decimal(
            price
        ),
        "active": bool(
            active
        ),
    }


# ================================================================
# CANDIDATE EVALUATION
# ================================================================

def evaluate_battery_candidate(
    battery: Any,
    system_voltage: Any,
    required_storage_wh: Any,
    required_continuous_current: Any = ZERO,
    inverter_efficiency: Any = Decimal("0.95"),
) -> Dict[str, Any]:
    """
    Fully evaluate one battery model.

    This function does not choose the battery.
    It calculates what the selected battery would require.
    """

    record = normalize_battery_record(
        battery
    )

    system = to_decimal(
        system_voltage
    )

    required_energy = non_negative(
        required_storage_wh
    )

    required_current = non_negative(
        required_continuous_current
    )

    battery_voltage = record[
        "voltage"
    ]

    battery_capacity = record[
        "capacity_ah"
    ]

    if system <= ZERO:
        return {
            "compatible": False,
            "selection_status": "invalid_system_voltage",
            "reason": (
                "System voltage is invalid."
            ),
            "battery": record,
        }

    if battery_voltage <= ZERO:
        return {
            "compatible": False,
            "selection_status": "invalid_battery_voltage",
            "reason": (
                "Battery nominal voltage is invalid."
            ),
            "battery": record,
        }

    if battery_capacity <= ZERO:
        return {
            "compatible": False,
            "selection_status": "invalid_capacity",
            "reason": (
                "Battery capacity is invalid."
            ),
            "battery": record,
        }

    # ------------------------------------------------------------
    # SERIES CONFIGURATION
    # ------------------------------------------------------------

    series_count = calculate_series_count(
        system,
        battery_voltage,
    )

    voltage_check = (
        evaluate_voltage_compatibility(
            system_voltage=system,
            battery_voltage=battery_voltage,
            series_count=series_count,
        )
    )

    if not voltage_check[
        "compatible"
    ]:

        return {
            "compatible": False,
            "selection_status": (
                "voltage_incompatible"
            ),
            "reason": voltage_check[
                "reason"
            ],
            "battery": record,
            "series_count": series_count,
            "actual_bank_voltage": (
                voltage_check.get(
                    "actual_bank_voltage",
                    ZERO,
                )
            ),
        }

    # ------------------------------------------------------------
    # REQUIRED CAPACITY
    # ------------------------------------------------------------

    dod = record[
        "depth_of_discharge"
    ]

    efficiency = record[
        "efficiency"
    ]

    # Energy available from one battery after DoD and efficiency.
    one_battery_usable_energy = (
        battery_voltage
        * battery_capacity
        * dod
        * efficiency
    )

    if one_battery_usable_energy <= ZERO:
        return {
            "compatible": False,
            "selection_status": (
                "invalid_energy_parameters"
            ),
            "reason": (
                "Battery usable-energy calculation "
                "is invalid."
            ),
            "battery": record,
        }

    # Number of parallel strings is derived from energy.
    #
    # One complete series string has:
    #
    #     series × battery usable energy
    #
    # because each battery in series increases voltage while Ah
    # remains the same.
    series_string_usable_energy = (
        one_battery_usable_energy
        * Decimal(series_count)
    )

    parallel_count = max(
        1,
        ceil_decimal(
            required_energy
            /
            series_string_usable_energy
        )
        if required_energy > ZERO
        else 1,
    )

    # ------------------------------------------------------------
    # COMPLETE BANK
    # ------------------------------------------------------------

    bank = calculate_battery_bank(
        battery_voltage=battery_voltage,
        battery_capacity_ah=battery_capacity,
        depth_of_discharge=dod,
        efficiency=efficiency,
        series_count=series_count,
        parallel_count=parallel_count,
    )

    total_quantity = (
        series_count
        * parallel_count
    )

    # ------------------------------------------------------------
    # DISCHARGE CAPABILITY
    # ------------------------------------------------------------

    bank_discharge_capability = (
        calculate_bank_discharge_capability(
            record[
                "max_discharge_current"
            ],
            parallel_count,
        )
    )

    discharge_check = (
        evaluate_discharge_capability(
            required_current=required_current,
            available_current=(
                bank_discharge_capability
            ),
        )
    )

    # ------------------------------------------------------------
    # EXCESS ENERGY
    # ------------------------------------------------------------

    energy_margin = (
        bank[
            "usable_energy_wh"
        ]
        -
        required_energy
    )

    energy_margin_percent = (
        (
            energy_margin
            /
            required_energy
            *
            HUNDRED
        )
        if required_energy > ZERO
        else ZERO
    )

    # ------------------------------------------------------------
    # COST
    # ------------------------------------------------------------

    total_price = (
        record[
            "price"
        ]
        * Decimal(total_quantity)
    )

    # ------------------------------------------------------------
    # SCORE
    # ------------------------------------------------------------

    score = calculate_candidate_score(
        battery=record,
        total_quantity=total_quantity,
        usable_energy=bank[
            "usable_energy_wh"
        ],
        required_energy=required_energy,
        discharge_pass=discharge_check[
            "pass"
        ],
        energy_margin_percent=(
            energy_margin_percent
        ),
    )

    # ------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------

    if not discharge_check[
        "pass"
    ]:

        selection_status = (
            "insufficient_discharge_capability"
        )

        compatible = False

        reason = (
            "Battery bank meets the energy requirement "
            "but does not provide adequate continuous "
            "discharge-current capability."
        )

    else:

        selection_status = "compatible"

        compatible = True

        reason = (
            "Battery model can form a bank that satisfies "
            "the calculated energy and continuous-current "
            "requirements."
        )

    # ------------------------------------------------------------
    # RESULT
    # ------------------------------------------------------------

    return {
        "compatible": compatible,

        "selection_status": selection_status,

        "reason": reason,

        "battery": record,

        "system_voltage": system,

        "series_count": series_count,

        "parallel_count": parallel_count,

        "total_quantity": total_quantity,

        "actual_bank_voltage": bank[
            "bank_voltage"
        ],

        "actual_bank_capacity_ah": bank[
            "bank_capacity_ah"
        ],

        "nominal_energy_wh": bank[
            "nominal_energy_wh"
        ],

        "usable_energy_wh": bank[
            "usable_energy_wh"
        ],

        "usable_energy_kwh": bank[
            "usable_energy_kwh"
        ],

        "required_energy_wh": required_energy,

        "energy_margin_wh": energy_margin,

        "energy_margin_percent": (
            energy_margin_percent
        ),

        "one_battery_usable_energy_wh": (
            one_battery_usable_energy
        ),

        "series_string_usable_energy_wh": (
            series_string_usable_energy
        ),

        "bank_max_discharge_current": (
            bank_discharge_capability
        ),

        "required_continuous_current": (
            required_current
        ),

        "discharge_check": discharge_check,

        "total_price": total_price,

        "score": score,
    }


# ================================================================
# CANDIDATE SCORING
# ================================================================

def calculate_candidate_score(
    battery: Dict[str, Any],
    total_quantity: int,
    usable_energy: Decimal,
    required_energy: Decimal,
    discharge_pass: bool,
    energy_margin_percent: Decimal,
) -> Decimal:
    """
    Rank battery candidates.

    The score is intentionally transparent.

    Factors:

        - lithium preference
        - fewer physical batteries
        - reasonable energy oversizing
        - discharge capability
        - warranty
        - cycle life

    Price is NOT the only criterion.

    A very cheap battery that cannot safely support the required
    current should not win merely because it costs less.
    """

    score = ZERO

    battery_type = battery.get(
        "battery_type",
        "",
    )

    score += (
        BATTERY_TYPE_PREFERENCE.get(
            battery_type,
            Decimal("0.50"),
        )
        * Decimal("25")
    )

    # Fewer physical batteries is generally preferable.
    if total_quantity <= 1:
        quantity_score = Decimal("20")
    elif total_quantity <= 4:
        quantity_score = Decimal("17")
    elif total_quantity <= 8:
        quantity_score = Decimal("14")
    elif total_quantity <= 16:
        quantity_score = Decimal("10")
    elif total_quantity <= 24:
        quantity_score = Decimal("6")
    else:
        quantity_score = Decimal("2")

    score += quantity_score

    # Energy oversizing.
    if required_energy > ZERO:

        ratio = (
            usable_energy
            /
            required_energy
        )

        if ratio >= Decimal("1.0") and ratio <= Decimal("1.30"):
            score += Decimal("20")
        elif ratio <= Decimal("1.50"):
            score += Decimal("16")
        elif ratio <= Decimal("2.0"):
            score += Decimal("10")
        else:
            score += Decimal("4")

    if discharge_pass:
        score += Decimal("20")
    else:
        score -= Decimal("30")

    warranty = to_decimal(
        battery.get(
            "warranty_years",
            0,
        )
    )

    score += min(
        warranty,
        Decimal("10"),
    )

    cycles = to_decimal(
        battery.get(
            "cycles",
            0,
        )
    )

    if cycles >= Decimal("6000"):
        score += Decimal("5")
    elif cycles >= Decimal("4000"):
        score += Decimal("4")
    elif cycles >= Decimal("3000"):
        score += Decimal("3")
    elif cycles >= Decimal("2000"):
        score += Decimal("2")
    elif cycles > ZERO:
        score += Decimal("1")

    return max(
        ZERO,
        score,
    )


# ================================================================
# BATTERY CATALOGUE SELECTION
# ================================================================

def select_battery_from_candidates(
    candidates: Iterable[Any],
    system_voltage: Any,
    required_storage_wh: Any,
    required_continuous_current: Any = ZERO,
    inverter_efficiency: Any = Decimal("0.95"),
) -> Dict[str, Any]:
    """
    Evaluate all supplied battery candidates and select the best
    compatible battery configuration.

    The caller may pass:

        Battery QuerySet
        list[Battery]
        list[dict]
    """

    system = to_decimal(
        system_voltage
    )

    required_energy = non_negative(
        required_storage_wh
    )

    required_current = non_negative(
        required_continuous_current
    )

    if system <= ZERO:
        return {
            "success": False,
            "selected": {},
            "candidates": [],
            "warnings": [
                "A valid system voltage is required."
            ],
            "message": (
                "Battery selection cannot proceed "
                "without a valid system voltage."
            ),
        }

    if required_energy <= ZERO:
        return {
            "success": False,
            "selected": {},
            "candidates": [],
            "warnings": [
                "Required battery storage energy is zero."
            ],
            "message": (
                "A valid daily energy/autonomy requirement "
                "is required before battery selection."
            ),
        }

    evaluated = []

    for battery in candidates:

        try:
            result = evaluate_battery_candidate(
                battery=battery,
                system_voltage=system,
                required_storage_wh=(
                    required_energy
                ),
                required_continuous_current=(
                    required_current
                ),
                inverter_efficiency=(
                    inverter_efficiency
                ),
            )

            evaluated.append(
                result
            )

        except (
            ValueError,
            InvalidOperation,
            TypeError,
        ) as exc:

            evaluated.append(
                {
                    "compatible": False,
                    "selection_status": (
                        "evaluation_error"
                    ),
                    "reason": str(exc),
                    "battery": normalize_battery_record(
                        battery
                    ),
                    "score": ZERO,
                }
            )

    compatible = [
        item
        for item in evaluated
        if item.get(
            "compatible",
            False,
        )
    ]

    compatible.sort(
        key=lambda item: (
            item.get(
                "score",
                ZERO,
            ),
            -item.get(
                "total_price",
                ZERO,
            ),
        ),
        reverse=True,
    )

    # ------------------------------------------------------------
    # NO COMPATIBLE BATTERY
    # ------------------------------------------------------------

    if not compatible:

        warnings = [
            "No battery in the supplied catalogue can satisfy "
            "the calculated storage and discharge requirements."
        ]

        if evaluated:
            warnings.append(
                "Review battery voltage, capacity, DoD, "
                "discharge-current rating and system voltage."
            )
        else:
            warnings.append(
                "No active battery candidates were supplied."
            )

        return {
            "success": False,
            "selected": {},
            "candidates": (
                serialize_candidate_results(
                    evaluated
                )
            ),
            "warnings": warnings,
            "message": (
                "Automatic battery selection failed."
            ),
        }

    selected = compatible[0]

    # ------------------------------------------------------------
    # WARNINGS
    # ------------------------------------------------------------

    warnings = []

    if selected[
        "energy_margin_percent"
    ] > Decimal("50"):

        warnings.append(
            "Selected battery bank has more than 50% "
            "usable-energy margin above the calculated "
            "requirement. Review whether a smaller "
            "configuration is commercially preferable."
        )

    if selected[
        "total_quantity"
    ] > 16:

        warnings.append(
            "The selected battery bank contains a large "
            "number of individual batteries. A higher-capacity "
            "battery may reduce series/parallel complexity."
        )

    if (
        selected[
            "battery"
        ][
            "battery_type"
        ]
        == "lead_acid"
    ):

        warnings.append(
            "Lead-acid battery selection requires adequate "
            "ventilation, maintenance and installation "
            "clearance according to the battery manufacturer."
        )

    if selected[
        "actual_bank_voltage"
    ] != system:

        warnings.append(
            "Actual battery-bank nominal voltage differs from "
            "the nominal system class because of the selected "
            "battery's individual nominal voltage. Exact "
            "inverter DC operating-range compatibility must "
            "be verified in the inverter-selection phase."
        )

    return {
        "success": True,

        "selected": serialize_candidate_result(
            selected
        ),

        "candidates": (
            serialize_candidate_results(
                evaluated
            )
        ),

        "warnings": warnings,

        "message": (
            "Battery model and bank configuration selected "
            "successfully."
        ),
    }


# ================================================================
# FULL PHASE 3 ENGINE
# ================================================================

def calculate_battery_system(
    load_result: Dict[str, Any],
    voltage_result: Dict[str, Any],
    battery_candidates: Iterable[Any],
    autonomy_days: Any = None,
    reserve_factor: Any = DEFAULT_SYSTEM_RESERVE,
    inverter_efficiency: Any = Decimal("0.95"),
) -> Dict[str, Any]:
    """
    Main Phase 3 entry point.

    Inputs
    ------

    load_result:
        Phase 1 result.

    voltage_result:
        Phase 2 result.

    battery_candidates:
        Active Battery objects or dictionaries.

    autonomy_days:
        Required battery autonomy in days.

    reserve_factor:
        Additional design reserve.

    inverter_efficiency:
        Expected inverter efficiency.

    Output
    ------

    A complete JSON-serializable battery result.
    """

    # ------------------------------------------------------------
    # INPUT VALIDATION
    # ------------------------------------------------------------

    if not isinstance(
        load_result,
        dict,
    ):

        return failed_result(
            "Load-engine result must be a dictionary."
        )

    if not isinstance(
        voltage_result,
        dict,
    ):

        return failed_result(
            "Voltage-engine result must be a dictionary."
        )

    # ------------------------------------------------------------
    # SYSTEM VOLTAGE
    # ------------------------------------------------------------

    system_voltage = extract_system_voltage(
        voltage_result
    )

    if system_voltage <= ZERO:

        return failed_result(
            "A valid system voltage from Phase 2 "
            "is required before battery selection."
        )

    # ------------------------------------------------------------
    # DAILY ENERGY
    # ------------------------------------------------------------

    daily_energy = extract_daily_energy(
        load_result
    )

    if daily_energy <= ZERO:

        return failed_result(
            "The load result does not contain enough information "
            "to calculate daily energy. Provide daily_energy_wh "
            "or load_watts with daily_operating_hours."
        )

    # ------------------------------------------------------------
    # AUTONOMY
    # ------------------------------------------------------------

    days = extract_autonomy_days(
        load_result,
        autonomy_days,
    )

    # ------------------------------------------------------------
    # STORAGE ENERGY
    # ------------------------------------------------------------

    storage = (
        calculate_required_storage_energy(
            daily_energy_wh=daily_energy,
            autonomy_days=days,
            reserve_factor=reserve_factor,
        )
    )

    required_storage_wh = storage[
        "design_energy_wh"
    ]

    # ------------------------------------------------------------
    # LOAD CURRENT
    # ------------------------------------------------------------
    # ------------------------------------------------------------
# LOAD POWER EXTRACTION
# ------------------------------------------------------------

    calculations = load_result.get(
        "calculations",
        {}
    )

    selected_load = load_result.get(
        "selected",
        {}
    )

    if not isinstance(calculations, dict):
        calculations = {}

    if not isinstance(selected_load, dict):
        selected_load = {}

    continuous_load = non_negative(
        calculations.get(
            "running_peak_load_w",
            selected_load.get(
                "peak_load_w",
                load_result.get(
                    "load_watts",
                    load_result.get(
                        "running_load",
                        0,
                    ),
                ),
            ),
        )
    )

    # continuous_load = non_negative(
    #     load_result.get(
    #         "load_watts",
    #         load_result.get(
    #             "running_load",
    #             0,
    #         ),
    #     )
    # )

    surge_load = non_negative(
        calculations.get(
            "surge_peak_load_w",
            selected_load.get(
                "surge_load_w",
                load_result.get(
                    "surge_watts",
                    load_result.get(
                        "surge_load",
                        continuous_load,
                    ),
                ),
            ),
        )
    )
    
    inverter_efficiency_normalized = (
        normalize_efficiency(
            inverter_efficiency,
            Decimal("0.95"),
        )
    )

    required_continuous_current = (
        calculate_required_battery_current(
            power_watts=continuous_load,
            bank_voltage=system_voltage,
            inverter_efficiency=(
                inverter_efficiency_normalized
            ),
        )
    )

    required_surge_current = (
        calculate_required_battery_current(
            power_watts=surge_load,
            bank_voltage=system_voltage,
            inverter_efficiency=(
                inverter_efficiency_normalized
            ),
        )
    )

    # ------------------------------------------------------------
    # CANDIDATE SELECTION
    # ------------------------------------------------------------

    selection = (
        select_battery_from_candidates(
            candidates=battery_candidates,
            system_voltage=system_voltage,
            required_storage_wh=(
                required_storage_wh
            ),
            required_continuous_current=(
                required_continuous_current
            ),
            inverter_efficiency=(
                inverter_efficiency_normalized
            ),
        )
    )

    if not selection[
        "success"
    ]:

        return {
            "success": False,

            "system_voltage": output_number(
                system_voltage
            ),

            "required": {
                "daily_energy_wh": output_number(
                    daily_energy
                ),
                "autonomy_days": output_number(
                    days
                ),
                "required_storage_wh": output_number(
                    required_storage_wh
                ),
                "required_storage_kwh": output_number(
                    required_storage_wh
                    / Decimal("1000")
                ),
                "required_continuous_current": (
                    output_number(
                        required_continuous_current
                    )
                ),
                "required_surge_current": (
                    output_number(
                        required_surge_current
                    )
                ),
            },

            "selected": {},

            "candidates": selection[
                "candidates"
            ],

            "warnings": selection[
                "warnings"
            ],

            "messages": [],

            "engine": ENGINE_NAME,

            "engine_version": ENGINE_VERSION,

            "message": selection[
                "message"
            ],
        }

    selected = selection[
        "selected"
    ]

    # ------------------------------------------------------------
    # FINAL WARNINGS
    # ------------------------------------------------------------

    warnings = list(
        selection.get(
            "warnings",
            [],
        )
    )

    messages = []

    messages.append(
        f"{output_number(system_voltage)} V nominal "
        "system voltage received from Phase 2."
    )

    messages.append(
        f"{selected['total_quantity']} battery/batteries "
        "required in the selected configuration."
    )

    messages.append(
        f"{selected['series_count']} batteries in series "
        f"and {selected['parallel_count']} parallel string(s)."
    )

    messages.append(
        f"Actual nominal battery-bank voltage: "
        f"{selected['actual_bank_voltage']} V."
    )

    messages.append(
        f"Usable battery energy: "
        f"{selected['usable_energy_kwh']} kWh."
    )

    # ------------------------------------------------------------
    # FINAL RESULT
    # ------------------------------------------------------------

    return {
        "success": True,

        # --------------------------------------------------------
        # CANONICAL SYSTEM VOLTAGE
        # --------------------------------------------------------

        "system_voltage": output_number(
            system_voltage
        ),

        # --------------------------------------------------------
        # STORAGE REQUIREMENT
        # --------------------------------------------------------

        "required": {
            "daily_energy_wh": output_number(
                daily_energy
            ),

            "daily_energy_kwh": output_number(
                daily_energy
                / Decimal("1000")
            ),

            "autonomy_days": output_number(
                days
            ),

            "reserve_factor": output_number(
                reserve_factor
            ),

            "required_storage_wh": output_number(
                required_storage_wh
            ),

            "required_storage_kwh": output_number(
                required_storage_wh
                / Decimal("1000")
            ),

            "continuous_load_watts": output_number(
                continuous_load
            ),

            "surge_load_watts": output_number(
                surge_load
            ),

            "required_continuous_current": (
                output_number(
                    required_continuous_current
                )
            ),

            "required_surge_current": (
                output_number(
                    required_surge_current
                )
            ),

            "inverter_efficiency": output_number(
                inverter_efficiency_normalized,
                places=4,
            ),
        },

        # --------------------------------------------------------
        # SELECTED BATTERY BANK
        # --------------------------------------------------------

        "selected": selected,

        # --------------------------------------------------------
        # ALL CANDIDATES
        # --------------------------------------------------------

        "candidates": selection[
            "candidates"
        ],

        # --------------------------------------------------------
        # MESSAGES / WARNINGS
        # --------------------------------------------------------

        "warnings": warnings,

        "messages": messages,

        # --------------------------------------------------------
        # ENGINE METADATA
        # --------------------------------------------------------

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        "message": (
            "Battery model and battery-bank configuration "
            "calculated successfully."
        ),
    }


# ================================================================
# SERIALIZATION
# ================================================================

def serialize_battery_record(
    battery: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Serialize normalized battery information.
    """

    return {
        "id": battery.get(
            "id"
        ),

        "brand": battery.get(
            "brand",
            "",
        ),
        "name": battery.get("name", ""),

        "model": battery.get(
            "model",
            "",
        ),

        "battery_type": battery.get(
            "battery_type",
            "",
        ),

        "voltage": output_number(
            battery.get(
                "voltage",
                ZERO,
            )
        ),

        "capacity_ah": output_number(
            battery.get(
                "capacity_ah",
                ZERO,
            )
        ),

        "depth_of_discharge": output_number(
            battery.get(
                "depth_of_discharge",
                ZERO,
            ),
            places=4,
        ),

        "efficiency": output_number(
            battery.get(
                "efficiency",
                ZERO,
            ),
            places=4,
        ),

        "max_discharge_current": output_number(
            battery.get(
                "max_discharge_current",
                ZERO,
            )
        ),

        "max_charge_current": output_number(
            battery.get(
                "max_charge_current",
                ZERO,
            )
        ),

        "warranty_years": int(
            battery.get(
                "warranty_years",
                0,
            )
        ),

        "weight": output_number(
            battery.get(
                "weight",
                ZERO,
            )
        ),

        "cycles": int(
            battery.get(
                "cycles",
                0,
            )
        ),

        "price": output_number(
            battery.get(
                "price",
                ZERO,
            )
        ),

        "active": bool(
            battery.get(
                "active",
                True,
            )
        ),
    }


def serialize_candidate_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert an evaluated battery candidate to a JSON-safe result.
    """

    battery = result.get(
        "battery",
        {},
    )

    serialized = {
        "compatible": bool(
            result.get(
                "compatible",
                False,
            )
        ),

        "selection_status": result.get(
            "selection_status",
            "",
        ),

        "reason": result.get(
            "reason",
            "",
        ),

        "battery": serialize_battery_record(
            battery
        ),

        "system_voltage": output_number(
            result.get(
                "system_voltage",
                ZERO,
            )
        ),

        "series_count": int(
            result.get(
                "series_count",
                0,
            )
        ),

        "parallel_count": int(
            result.get(
                "parallel_count",
                0,
            )
        ),

        "total_quantity": int(
            result.get(
                "total_quantity",
                0,
            )
        ),

        "actual_bank_voltage": output_number(
            result.get(
                "actual_bank_voltage",
                ZERO,
            )
        ),

        "actual_bank_capacity_ah": output_number(
            result.get(
                "actual_bank_capacity_ah",
                ZERO,
            )
        ),

        "nominal_energy_wh": output_number(
            result.get(
                "nominal_energy_wh",
                ZERO,
            )
        ),

        "usable_energy_wh": output_number(
            result.get(
                "usable_energy_wh",
                ZERO,
            )
        ),

        "usable_energy_kwh": output_number(
            result.get(
                "usable_energy_kwh",
                ZERO,
            )
        ),

        "required_energy_wh": output_number(
            result.get(
                "required_energy_wh",
                ZERO,
            )
        ),

        "energy_margin_wh": output_number(
            result.get(
                "energy_margin_wh",
                ZERO,
            )
        ),

        "energy_margin_percent": output_number(
            result.get(
                "energy_margin_percent",
                ZERO,
            )
        ),

        "one_battery_usable_energy_wh": output_number(
            result.get(
                "one_battery_usable_energy_wh",
                ZERO,
            )
        ),

        "series_string_usable_energy_wh": output_number(
            result.get(
                "series_string_usable_energy_wh",
                ZERO,
            )
        ),

        "bank_max_discharge_current": output_number(
            result.get(
                "bank_max_discharge_current",
                ZERO,
            )
        ),

        "required_continuous_current": output_number(
            result.get(
                "required_continuous_current",
                ZERO,
            )
        ),

        "total_price": output_number(
            result.get(
                "total_price",
                ZERO,
            )
        ),

        "score": output_number(
            result.get(
                "score",
                ZERO,
            )
        ),
    }

    discharge_check = result.get(
        "discharge_check"
    )

    if isinstance(
        discharge_check,
        dict,
    ):

        serialized[
            "discharge_check"
        ] = {
            "pass": bool(
                discharge_check.get(
                    "pass",
                    False,
                )
            ),

            "required_current": output_number(
                discharge_check.get(
                    "required_current",
                    ZERO,
                )
            ),

            "available_current": output_number(
                discharge_check.get(
                    "available_current",
                    ZERO,
                )
            ),

            "design_available_current": (
                output_number(
                    discharge_check.get(
                        "design_available_current",
                        ZERO,
                    )
                )
            ),

            "utilization": output_number(
                discharge_check.get(
                    "utilization",
                    ZERO,
                ),
                places=4,
            ),

            "margin_current": output_number(
                discharge_check.get(
                    "margin_current",
                    ZERO,
                )
            ),

            "reason": discharge_check.get(
                "reason",
                "",
            ),
        }

    return serialized


def serialize_candidate_results(
    results: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Serialize a collection of candidate results.
    """

    return [
        serialize_candidate_result(
            result
        )
        for result in results
    ]


# ================================================================
# FAILURE RESULT
# ================================================================

def failed_result(
    message: str,
) -> Dict[str, Any]:
    """
    Standard Phase 3 failure contract.
    """

    return {
        "success": False,

        "system_voltage": None,

        "required": {},

        "selected": {},

        "candidates": [],

        "warnings": [
            message
        ],

        "messages": [],

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        "message": message,
    }


# ================================================================
# PUBLIC ALIASES
# ================================================================

# Primary public name.
calculate_battery = calculate_battery_system

# Alternative explicit name.
run_battery_engine = calculate_battery_system

# Candidate selection helper.
select_battery = select_battery_from_candidates
