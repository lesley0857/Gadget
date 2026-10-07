"""
solar/services/protection_engine.py

PHASE 8
PROTECTION ENGINE

Responsibilities
----------------
This engine determines the engineering requirements for protective
devices in a solar PV system.

It does NOT:

    - select batteries
    - select solar panels
    - select inverters
    - select charge controllers
    - size cables
    - calculate pricing
    - query product inventory
    - create BOQs

Protection covered
------------------
    1. PV string / array overcurrent protection
    2. Battery DC overcurrent protection
    3. AC inverter output overcurrent protection
    4. PV DC isolator
    5. AC isolator
    6. PV DC SPD
    7. AC SPD

Engineering principle
--------------------
Protection is sized from the electrical characteristics produced
by the preceding engineering phases.

The engine therefore works from:

    PV current
    PV Isc
    PV corrected Voc
    PV string count
    battery/system voltage
    inverter DC current
    inverter AC output current
    inverter AC voltage

The engine does NOT assume that a protection device exists in the
database. Product selection belongs to a later product-selection/
BOQ layer.

Standards basis
---------------
The engineering logic is aligned with the protection concepts of:

    IEC 62548-1
        PV array design requirements.

    IEC 60269-6
        PV fuse-links.

    IEC 61643-31
        Surge protective devices for photovoltaic DC systems.

Important
---------
The numerical values produced by this engine are engineering
recommendations. Final device selection must still verify:

    - device voltage rating
    - interrupting/breaking capacity
    - DC/AC suitability
    - manufacturer specifications
    - installation environment
    - temperature derating
    - earthing arrangement
    - short-circuit level
    - local electrical regulations
    - coordination with upstream/downstream protection

Input
-----
The preferred public API is:

    calculate_protection(
        panel_result=...,
        inverter_result=...,
        system_voltage=...,
        battery_result=...,
        inverter_ac_voltage=230,
    )

The engine also accepts a normalized engineering dictionary.

Output
------
A standardized result:

{
    "success": True,
    "required": {...},
    "selected": {...},
    "devices": {...},
    "analysis": {...},
    "warnings": [...],
    "messages": [...],
    "candidates": [...]
}

No Django model objects are returned.
All final numeric values are JSON-safe.
"""

from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_HALF_UP,
)
from typing import Any, Dict, Iterable, List, Optional


# ======================================================================
# DECIMAL CONSTANTS
# ======================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")


# ======================================================================
# ENGINE METADATA
# ======================================================================

ENGINE_NAME = "Protection Engine"
ENGINE_VERSION = "1.0.0"


# ======================================================================
# ENGINEERING DEFAULTS
# ======================================================================

# General overcurrent design factor.
DEFAULT_OVERCURRENT_FACTOR = Decimal("1.25")

# PV string protection criterion.
PV_FUSE_MIN_FACTOR = Decimal("1.50")
PV_FUSE_MAX_FACTOR = Decimal("2.40")

# PV isolator continuous current design factor.
PV_ISOLATOR_CURRENT_FACTOR = Decimal("1.25")

# Battery protection design factor.
BATTERY_PROTECTION_FACTOR = Decimal("1.25")

# AC protection design factor.
AC_PROTECTION_FACTOR = Decimal("1.25")

# AC isolator design factor.
AC_ISOLATOR_CURRENT_FACTOR = Decimal("1.25")

# Small engineering margin used for voltage selection.
VOLTAGE_MARGIN = Decimal("1.10")

# Default AC voltage.
DEFAULT_AC_VOLTAGE = Decimal("230")


# ======================================================================
# STANDARD DEVICE RATINGS
# ======================================================================

STANDARD_CURRENT_RATINGS = (
    Decimal("2"),
    Decimal("4"),
    Decimal("6"),
    Decimal("10"),
    Decimal("13"),
    Decimal("16"),
    Decimal("20"),
    Decimal("25"),
    Decimal("32"),
    Decimal("40"),
    Decimal("50"),
    Decimal("63"),
    Decimal("80"),
    Decimal("100"),
    Decimal("125"),
    Decimal("160"),
    Decimal("200"),
    Decimal("250"),
    Decimal("315"),
    Decimal("355"),
    Decimal("400"),
    Decimal("500"),
    Decimal("630"),
    Decimal("800"),
    Decimal("1000"),
    Decimal("1250"),
    Decimal("1600"),
)


# Common PV/DC isolator voltage classes.
DC_ISOLATOR_VOLTAGES = (
    Decimal("150"),
    Decimal("250"),
    Decimal("400"),
    Decimal("500"),
    Decimal("600"),
    Decimal("800"),
    Decimal("1000"),
    Decimal("1200"),
    Decimal("1500"),
)


# Common PV SPD voltage classes.
DC_SPD_VOLTAGES = (
    Decimal("150"),
    Decimal("250"),
    Decimal("400"),
    Decimal("600"),
    Decimal("800"),
    Decimal("1000"),
    Decimal("1200"),
    Decimal("1500"),
)


# Common AC SPD Uc ratings.
AC_SPD_VOLTAGES = (
    Decimal("275"),
    Decimal("320"),
    Decimal("385"),
    Decimal("440"),
),
# Correct tuple shape below.
AC_SPD_VOLTAGES = AC_SPD_VOLTAGES[0]


# ======================================================================
# SAFE DECIMAL UTILITIES
# ======================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
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
        TypeError,
        ValueError,
    ):
        return default


def positive_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a positive Decimal or default.
    """

    number = to_decimal(
        value,
        default=default,
    )

    if number <= ZERO:
        return default

    return number


def non_negative_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a non-negative Decimal.
    """

    number = to_decimal(
        value,
        default=default,
    )

    if number < ZERO:
        return ZERO

    return number


def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Consistent engineering rounding.
    """

    number = to_decimal(value)

    quantum = Decimal(
        "1"
    ).scaleb(
        -places
    )

    return number.quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )


def output_number(
    value: Any,
    places: int = 2,
):
    """
    Convert Decimal to JSON/template-friendly number.
    """

    number = round_decimal(
        value,
        places=places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


def ceil_decimal(
    value: Any,
) -> int:
    """
    Ceiling to the next whole number.
    """

    number = to_decimal(value)

    return int(
        number.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


# ======================================================================
# STANDARD RATING SELECTION
# ======================================================================

def select_standard_current(
    required_current: Any,
) -> Optional[int]:
    """
    Select the smallest standard protective-device current rating
    greater than or equal to the calculated required current.

    Example:

        required = 21 A
        selected = 25 A
    """

    required = positive_decimal(
        required_current
    )

    if required <= ZERO:
        return None

    for rating in STANDARD_CURRENT_RATINGS:
        if rating >= required:
            return int(rating)

    return int(
        STANDARD_CURRENT_RATINGS[-1]
    )


def select_standard_voltage(
    required_voltage: Any,
    voltage_classes: Iterable[Decimal],
) -> Optional[int]:
    """
    Select the smallest standard device voltage rating greater than
    or equal to the required voltage.
    """

    required = positive_decimal(
        required_voltage
    )

    if required <= ZERO:
        return None

    for voltage in voltage_classes:
        if voltage >= required:
            return int(voltage)

    return None


# ======================================================================
# INPUT EXTRACTION HELPERS
# ======================================================================

def _first_value(
    source: Optional[Dict[str, Any]],
    keys: Iterable[str],
    default: Any = ZERO,
) -> Any:
    """
    Return the first existing/non-null key from a dictionary.
    """

    if not isinstance(source, dict):
        return default

    for key in keys:
        if key in source and source[key] is not None:
            return source[key]

    return default


def _nested_first(
    source: Optional[Dict[str, Any]],
    sections: Iterable[str],
    keys: Iterable[str],
    default: Any = ZERO,
) -> Any:
    """
    Search common result sections.

    This gives Phase 8 a stable boundary even if an earlier engine
    places engineering values under required/selected/analysis.
    """

    if not isinstance(source, dict):
        return default

    for section in sections:

        section_data = source.get(
            section
        )

        if not isinstance(
            section_data,
            dict,
        ):
            continue

        value = _first_value(
            section_data,
            keys,
            default=None,
        )

        if value is not None:
            return value

    return _first_value(
        source,
        keys,
        default=default,
    )


# ======================================================================
# NORMALIZED INPUT
# ======================================================================

def normalize_protection_inputs(
    panel_result: Optional[Dict[str, Any]] = None,
    inverter_result: Optional[Dict[str, Any]] = None,
    system_voltage: Any = None,
    battery_result: Optional[Dict[str, Any]] = None,
    inverter_ac_voltage: Any = DEFAULT_AC_VOLTAGE,
    *,
    pv_current: Any = None,
    pv_isc: Any = None,
    pv_voc: Any = None,
    pv_string_count: Any = None,
    inverter_dc_current: Any = None,
    inverter_ac_current: Any = None,
) -> Dict[str, Any]:
    """
    Normalize the outputs of Phases 4-7 into one Phase-8 input.

    Explicit keyword values take precedence over values extracted
    from previous engine results.
    """

    # --------------------------------------------------------------
    # PV CURRENT
    # --------------------------------------------------------------

    if pv_current is None:
        pv_current = _nested_first(
            panel_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "array_current",
                "operating_current",
                "pv_current",
                "current",
            ),
        )

    if pv_isc is None:
        pv_isc = _nested_first(
            panel_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "array_isc",
                "isc",
                "short_circuit_current",
                "string_isc",
            ),
        )

    if pv_voc is None:
        pv_voc = _nested_first(
            panel_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "corrected_voc",
                "array_voc",
                "voc",
                "open_circuit_voltage",
            ),
        )

    if pv_string_count is None:
        pv_string_count = _nested_first(
            panel_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "parallel",
                "parallel_strings",
                "string_count",
                "strings",
            ),
        )

    # --------------------------------------------------------------
    # SYSTEM VOLTAGE
    # --------------------------------------------------------------

    if system_voltage is None:
        system_voltage = _first_value(
            battery_result,
            (
                "system_voltage",
                "selected_voltage",
                "nominal_system_voltage",
            ),
            default=None,
        )

    if system_voltage is None:
        system_voltage = _nested_first(
            battery_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "system_voltage",
                "battery_voltage",
                "nominal_system_voltage",
            ),
            default=ZERO,
        )

    # --------------------------------------------------------------
    # BATTERY ACTUAL BANK VOLTAGE
    # --------------------------------------------------------------

    actual_battery_voltage = _nested_first(
        battery_result,
        sections=(
            "selected",
            "required",
            "analysis",
        ),
        keys=(
            "actual_bank_voltage",
            "battery_bank_voltage",
            "bank_voltage",
        ),
        default=None,
    )

    if actual_battery_voltage is None:
        actual_battery_voltage = system_voltage

    # --------------------------------------------------------------
    # INVERTER DC CURRENT
    # --------------------------------------------------------------

    if inverter_dc_current is None:
        inverter_dc_current = _nested_first(
            inverter_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "dc_current",
                "battery_current",
                "input_current",
                "estimated_dc_current",
            ),
        )

    # --------------------------------------------------------------
    # INVERTER AC CURRENT
    # --------------------------------------------------------------

    if inverter_ac_current is None:
        inverter_ac_current = _nested_first(
            inverter_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "output_current",
                "ac_current",
                "output_amps",
                "current",
            ),
        )

    # --------------------------------------------------------------
    # IF CURRENT IS NOT PROVIDED, CALCULATE FROM POWER
    # --------------------------------------------------------------

    inverter_power = _nested_first(
        inverter_result,
        sections=(
            "selected",
            "required",
            "analysis",
        ),
        keys=(
            "rated_power",
            "power",
            "continuous_power",
            "required_power",
        ),
        default=ZERO,
    )

    inverter_dc_power = _nested_first(
        inverter_result,
        sections=(
            "selected",
            "required",
            "analysis",
        ),
        keys=(
            "dc_power",
            "required_power",
            "continuous_power",
            "rated_power",
        ),
        default=inverter_power,
    )

    inverter_efficiency = _nested_first(
        inverter_result,
        sections=(
            "selected",
            "required",
            "analysis",
        ),
        keys=(
            "efficiency",
            "inverter_efficiency",
        ),
        default=Decimal("0.95"),
    )

    efficiency = to_decimal(
        inverter_efficiency,
        default=Decimal("0.95"),
    )

    if efficiency <= ZERO:
        efficiency = Decimal("0.95")

    if efficiency > ONE:
        efficiency /= HUNDRED

    if inverter_dc_current is None or to_decimal(
        inverter_dc_current
    ) <= ZERO:

        dc_voltage = positive_decimal(
            actual_battery_voltage,
            default=to_decimal(
                system_voltage
            ),
        )

        if (
            dc_voltage > ZERO
            and inverter_dc_power > ZERO
        ):
            inverter_dc_current = (
                inverter_dc_power
                /
                (
                    dc_voltage
                    * efficiency
                )
            )

    ac_voltage = positive_decimal(
        inverter_ac_voltage,
        default=DEFAULT_AC_VOLTAGE,
    )

    if (
        inverter_ac_current is None
        or to_decimal(
            inverter_ac_current
        ) <= ZERO
    ):

        phase = _nested_first(
            inverter_result,
            sections=(
                "selected",
                "required",
                "analysis",
            ),
            keys=(
                "phase",
                "phases",
            ),
            default="single_phase",
        )

        if inverter_power > ZERO:

            if str(phase).lower() == "three_phase":

                inverter_ac_current = (
                    inverter_power
                    /
                    (
                        Decimal("1.7320508075688772")
                        * ac_voltage
                    )
                )

            else:

                inverter_ac_current = (
                    inverter_power
                    / ac_voltage
                )

    return {
        "pv_current": positive_decimal(
            pv_current
        ),
        "pv_isc": positive_decimal(
            pv_isc
        ),
        "pv_voc": positive_decimal(
            pv_voc
        ),
        "pv_string_count": max(
            0,
            int(
                to_decimal(
                    pv_string_count
                )
            ),
        ),
        "system_voltage": positive_decimal(
            system_voltage
        ),
        "actual_battery_voltage": positive_decimal(
            actual_battery_voltage
        ),
        "inverter_dc_current": positive_decimal(
            inverter_dc_current
        ),
        "inverter_ac_current": positive_decimal(
            inverter_ac_current
        ),
        "inverter_ac_voltage": ac_voltage,
        "inverter_power": positive_decimal(
            inverter_power
        ),
        "inverter_efficiency": efficiency,
    }


# ======================================================================
# PV FUSE
# ======================================================================

def calculate_pv_fuse(
    string_isc: Any,
    parallel_strings: Any = 1,
) -> Dict[str, Any]:
    """
    Calculate PV string overcurrent protection.

    The calculation is based on the PV string short-circuit current.

    A string protection device is only normally required where
    parallel-string fault current can create a hazardous reverse
    current condition. For a single string, no string fuse is
    automatically required by this calculation.

    For designs requiring string OCPD:

        minimum design current > 1.5 × Isc

        maximum nominal protection
            <= 2.4 × Isc

    The selected device is the smallest standard rating above the
    calculated minimum.
    """

    isc = positive_decimal(
        string_isc
    )

    strings = max(
        1,
        int(
            to_decimal(
                parallel_strings,
                default=ONE,
            )
        ),
    )

    if isc <= ZERO:
        return {
            "success": False,
            "required": {
                "string_isc": 0,
                "minimum_rating": 0,
                "maximum_rating": 0,
            },
            "selected": None,
            "warnings": [
                "PV string short-circuit current is required."
            ],
            "message": (
                "PV fuse calculation cannot be completed "
                "without string Isc."
            ),
        }

    # --------------------------------------------------------------
    # SINGLE STRING
    # --------------------------------------------------------------

    if strings <= 1:

        return {
            "success": True,
            "required": {
                "string_isc": output_number(isc),
                "minimum_rating": output_number(
                    isc * PV_FUSE_MIN_FACTOR
                ),
                "maximum_rating": output_number(
                    isc * PV_FUSE_MAX_FACTOR
                ),
            },
            "selected": {
                "rating_a": None,
                "required": False,
                "type": "PV string fuse",
                "reason": (
                    "Only one PV string is present; "
                    "parallel-string reverse-current protection "
                    "is not required by this calculation."
                ),
            },
            "warnings": [],
            "message": (
                "No PV string fuse is required for a single "
                "parallel string by this calculation."
            ),
        }

    # --------------------------------------------------------------
    # MULTIPLE STRINGS
    # --------------------------------------------------------------

    minimum_rating = (
        isc
        * PV_FUSE_MIN_FACTOR
    )

    maximum_rating = (
        isc
        * PV_FUSE_MAX_FACTOR
    )

    selected_rating = select_standard_current(
        minimum_rating
    )

    warnings = []

    if selected_rating is None:

        return {
            "success": False,
            "required": {
                "string_isc": output_number(isc),
                "minimum_rating": output_number(
                    minimum_rating
                ),
                "maximum_rating": output_number(
                    maximum_rating
                ),
            },
            "selected": None,
            "warnings": [
                "Required PV fuse current exceeds "
                "the supported standard rating table."
            ],
            "message": (
                "No standard PV fuse rating could be selected."
            ),
        }

    if Decimal(selected_rating) > maximum_rating:

        warnings.append(
            "The next standard fuse rating exceeds the "
            "calculated maximum protection range. Verify the "
            "module maximum series-fuse rating and select a "
            "manufacturer-approved PV fuse."
        )

    return {
        "success": True,
        "required": {
            "string_isc": output_number(isc),
            "minimum_rating": output_number(
                minimum_rating
            ),
            "maximum_rating": output_number(
                maximum_rating
            ),
            "parallel_strings": strings,
        },
        "selected": {
            "rating_a": selected_rating,
            "required": True,
            "type": "PV string fuse",
            "standard": "IEC 60269-6",
        },
        "warnings": warnings,
        "message": (
            f"{selected_rating} A PV string overcurrent "
            "protection is recommended."
        ),
    }


# ======================================================================
# BATTERY BREAKER
# ======================================================================

def calculate_battery_breaker(
    dc_current: Any,
    battery_voltage: Any,
) -> Dict[str, Any]:
    """
    Calculate battery-side DC overcurrent protection.

    Required current:

        I_protection = 1.25 × I_dc

    The selected breaker must also have a DC voltage rating at least
    equal to the actual battery-bank voltage.

    Final interrupting capacity must be verified against the
    battery manufacturer's prospective short-circuit current.
    """

    current = positive_decimal(
        dc_current
    )

    voltage = positive_decimal(
        battery_voltage
    )

    if current <= ZERO:
        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "Battery DC current is required."
            ],
            "message": (
                "Battery breaker calculation cannot be "
                "completed without DC current."
            ),
        }

    if voltage <= ZERO:
        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "Battery/system voltage is required."
            ],
            "message": (
                "Battery breaker calculation cannot be "
                "completed without battery voltage."
            ),
        }

    required_current = (
        current
        * BATTERY_PROTECTION_FACTOR
    )

    rating = select_standard_current(
        required_current
    )

    warnings = []

    if rating is None:

        return {
            "success": False,
            "required": {
                "operating_current": output_number(
                    current
                ),
                "minimum_rating": output_number(
                    required_current
                ),
                "voltage_rating": output_number(
                    voltage
                ),
            },
            "selected": None,
            "warnings": [
                "Required battery protection current exceeds "
                "the supported standard rating table."
            ],
            "message": (
                "No standard battery breaker rating could "
                "be selected."
            ),
        }

    if voltage > Decimal("60"):

        warnings.append(
            "Battery voltage exceeds 60 V DC. "
            "Use a purpose-designed DC-rated protective device "
            "with an appropriate DC breaking capacity."
        )

    return {
        "success": True,
        "required": {
            "operating_current": output_number(
                current
            ),
            "minimum_rating": output_number(
                required_current
            ),
            "voltage_rating": output_number(
                voltage
            ),
        },
        "selected": {
            "rating_a": rating,
            "voltage_rating_v": output_number(
                voltage
            ),
            "type": "Battery DC circuit breaker",
            "pole_requirement": "DC-rated",
        },
        "warnings": warnings,
        "message": (
            f"{rating} A DC battery protection is "
            "recommended."
        ),
    }


# ======================================================================
# AC BREAKER
# ======================================================================

def calculate_ac_breaker(
    ac_current: Any,
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
) -> Dict[str, Any]:
    """
    Calculate inverter AC-side overcurrent protection.

    Required current:

        I_protection = 1.25 × I_output

    This is a sizing recommendation. Final breaker selection must
    additionally verify cable ampacity, prospective fault current,
    breaking capacity and upstream/downstream coordination.
    """

    current = positive_decimal(
        ac_current
    )

    voltage = positive_decimal(
        ac_voltage,
        default=DEFAULT_AC_VOLTAGE,
    )

    if current <= ZERO:
        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "AC output current is required."
            ],
            "message": (
                "AC breaker calculation cannot be completed "
                "without inverter output current."
            ),
        }

    required_current = (
        current
        * AC_PROTECTION_FACTOR
    )

    rating = select_standard_current(
        required_current
    )

    if rating is None:

        return {
            "success": False,
            "required": {
                "operating_current": output_number(
                    current
                ),
                "minimum_rating": output_number(
                    required_current
                ),
                "voltage": output_number(
                    voltage
                ),
            },
            "selected": None,
            "warnings": [
                "Required AC breaker current exceeds the "
                "supported standard rating table."
            ],
            "message": (
                "No standard AC breaker rating could "
                "be selected."
            ),
        }

    return {
        "success": True,
        "required": {
            "operating_current": output_number(
                current
            ),
            "minimum_rating": output_number(
                required_current
            ),
            "voltage": output_number(
                voltage
            ),
        },
        "selected": {
            "rating_a": rating,
            "voltage_rating_v": output_number(
                voltage
            ),
            "type": "AC circuit breaker",
        },
        "warnings": [],
        "message": (
            f"{rating} A AC output protection is "
            "recommended."
        ),
    }


# ======================================================================
# PV DC ISOLATOR
# ======================================================================

def calculate_pv_isolator(
    pv_current: Any,
    pv_voltage: Any,
) -> Dict[str, Any]:
    """
    Calculate PV DC isolator requirements.

    Current rating:

        >= 1.25 × PV operating current

    Voltage rating:

        >= corrected PV open-circuit voltage.

    The selected isolator must be specifically rated for DC PV
    switching duty.
    """

    current = positive_decimal(
        pv_current
    )

    voltage = positive_decimal(
        pv_voltage
    )

    if current <= ZERO or voltage <= ZERO:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "PV current and PV voltage are required "
                "for isolator sizing."
            ],
            "message": (
                "PV isolator calculation cannot be completed."
            ),
        }

    required_current = (
        current
        * PV_ISOLATOR_CURRENT_FACTOR
    )

    current_rating = select_standard_current(
        required_current
    )

    voltage_rating = select_standard_voltage(
        voltage,
        DC_ISOLATOR_VOLTAGES,
    )

    warnings = []

    if voltage_rating is None:

        warnings.append(
            "PV voltage exceeds the supported isolator "
            "voltage table."
        )

    if current_rating is None:

        warnings.append(
            "PV current exceeds the supported isolator "
            "current table."
        )

    success = (
        current_rating is not None
        and voltage_rating is not None
    )

    return {
        "success": success,
        "required": {
            "operating_current": output_number(
                current
            ),
            "minimum_current_rating": output_number(
                required_current
            ),
            "minimum_voltage_rating": output_number(
                voltage
            ),
        },
        "selected": (
            {
                "current_rating_a": current_rating,
                "voltage_rating_v": voltage_rating,
                "type": "PV DC isolator",
                "dc_rated": True,
            }
            if success
            else None
        ),
        "warnings": warnings,
        "message": (
            f"{current_rating} A / "
            f"{voltage_rating} V DC PV isolator "
            "is recommended."
            if success
            else
            "PV isolator requirements could not be "
            "fully satisfied."
        ),
    }


# ======================================================================
# AC ISOLATOR
# ======================================================================

def calculate_ac_isolator(
    ac_current: Any,
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
) -> Dict[str, Any]:
    """
    Calculate AC inverter-output isolator requirements.
    """

    current = positive_decimal(
        ac_current
    )

    voltage = positive_decimal(
        ac_voltage,
        default=DEFAULT_AC_VOLTAGE,
    )

    if current <= ZERO:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "AC output current is required."
            ],
            "message": (
                "AC isolator calculation cannot be completed."
            ),
        }

    required_current = (
        current
        * AC_ISOLATOR_CURRENT_FACTOR
    )

    rating = select_standard_current(
        required_current
    )

    if rating is None:

        return {
            "success": False,
            "required": {
                "operating_current": output_number(
                    current
                ),
                "minimum_rating": output_number(
                    required_current
                ),
                "voltage_rating": output_number(
                    voltage
                ),
            },
            "selected": None,
            "warnings": [
                "Required AC isolator current exceeds "
                "the supported standard rating table."
            ],
            "message": (
                "No standard AC isolator rating could "
                "be selected."
            ),
        }

    return {
        "success": True,
        "required": {
            "operating_current": output_number(
                current
            ),
            "minimum_current_rating": output_number(
                required_current
            ),
            "voltage_rating": output_number(
                voltage
            ),
        },
        "selected": {
            "current_rating_a": rating,
            "voltage_rating_v": output_number(
                voltage
            ),
            "type": "AC isolator",
        },
        "warnings": [],
        "message": (
            f"{rating} A AC isolator is recommended."
        ),
    }


# ======================================================================
# PV DC SPD
# ======================================================================

def calculate_dc_spd(
    pv_voltage: Any,
    *,
    spd_type: str = "type_2",
) -> Dict[str, Any]:
    """
    Determine the required PV DC SPD voltage class.

    The selected Ucpv must not be below the maximum PV operating
    voltage presented to the SPD.

    A 10% engineering voltage margin is used for the calculated
    minimum Ucpv.

    The engine does not determine lightning protection level.
    Type 1+2 versus Type 2 must be confirmed from the site's
    lightning protection/risk assessment and installation
    arrangement.
    """

    voltage = positive_decimal(
        pv_voltage
    )

    if voltage <= ZERO:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "Corrected PV open-circuit voltage is required."
            ],
            "message": (
                "PV DC SPD calculation cannot be completed."
            ),
        }

    minimum_ucpv = (
        voltage
        * VOLTAGE_MARGIN
    )

    selected_voltage = select_standard_voltage(
        minimum_ucpv,
        DC_SPD_VOLTAGES,
    )

    warnings = []

    if selected_voltage is None:

        warnings.append(
            "PV voltage exceeds the supported DC SPD "
            "voltage classes."
        )

    if spd_type not in (
        "type_2",
        "type_1_2",
    ):

        warnings.append(
            "Unsupported SPD type supplied. "
            "Type 2 has been used."
        )

        spd_type = "type_2"

    warnings.append(
        "Final PV SPD selection must verify Ucpv, Up, "
        "In/Imax, short-circuit withstand and the "
        "installation's lightning-risk requirements."
    )

    success = (
        selected_voltage is not None
    )

    return {
        "success": success,
        "required": {
            "pv_voltage": output_number(
                voltage
            ),
            "minimum_ucpv": output_number(
                minimum_ucpv
            ),
            "spd_type": spd_type,
        },
        "selected": (
            {
                "ucpv_v": selected_voltage,
                "type": (
                    "Type 1+2 PV DC SPD"
                    if spd_type == "type_1_2"
                    else "Type 2 PV DC SPD"
                ),
                "standard": "IEC 61643-31",
            }
            if success
            else None
        ),
        "warnings": warnings,
        "message": (
            f"{selected_voltage} V DC Ucpv "
            "SPD class is recommended."
            if success
            else
            "No compatible PV DC SPD voltage class "
            "was found."
        ),
    }


# ======================================================================
# AC SPD
# ======================================================================

def calculate_ac_spd(
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
    *,
    spd_type: str = "type_2",
) -> Dict[str, Any]:
    """
    Determine the AC SPD Uc requirement.

    For a normal 230 V single-phase system, 275 V is a common
    minimum Uc class.

    The engine deliberately does not infer the lightning-risk
    classification from voltage alone.
    """

    voltage = positive_decimal(
        ac_voltage,
        default=DEFAULT_AC_VOLTAGE,
    )

    # For a nominal 230 V line-neutral system:
    # 230 V × 1.10 = 253 V -> next common Uc = 275 V.
    required_uc = (
        voltage
        * VOLTAGE_MARGIN
    )

    selected_voltage = select_standard_voltage(
        required_uc,
        AC_SPD_VOLTAGES,
    )

    warnings = []

    if selected_voltage is None:

        warnings.append(
            "AC voltage exceeds the supported AC SPD "
            "voltage classes."
        )

    if spd_type not in (
        "type_2",
        "type_1_2",
    ):

        warnings.append(
            "Unsupported SPD type supplied. "
            "Type 2 has been used."
        )

        spd_type = "type_2"

    warnings.append(
        "Final AC SPD selection must verify Uc, Up, "
        "discharge current, short-circuit withstand and "
        "the site's lightning protection/risk assessment."
    )

    success = (
        selected_voltage is not None
    )

    return {
        "success": success,
        "required": {
            "system_voltage": output_number(
                voltage
            ),
            "minimum_uc": output_number(
                required_uc
            ),
            "spd_type": spd_type,
        },
        "selected": (
            {
                "uc_v": selected_voltage,
                "type": (
                    "Type 1+2 AC SPD"
                    if spd_type == "type_1_2"
                    else "Type 2 AC SPD"
                ),
            }
            if success
            else None
        ),
        "warnings": warnings,
        "message": (
            f"{selected_voltage} V AC Uc SPD class "
            "is recommended."
            if success
            else
            "No compatible AC SPD voltage class "
            "was found."
        ),
    }


# ======================================================================
# PROTECTION ENGINE
# ======================================================================

class ProtectionEngine:
    """
    Main Phase-8 protection engineering engine.
    """

    def __init__(
        self,
        panel_result: Optional[Dict[str, Any]] = None,
        inverter_result: Optional[Dict[str, Any]] = None,
        system_voltage: Any = None,
        battery_result: Optional[Dict[str, Any]] = None,
        inverter_ac_voltage: Any = DEFAULT_AC_VOLTAGE,
        *,
        pv_current: Any = None,
        pv_isc: Any = None,
        pv_voc: Any = None,
        pv_string_count: Any = None,
        inverter_dc_current: Any = None,
        inverter_ac_current: Any = None,
        dc_spd_type: str = "type_2",
        ac_spd_type: str = "type_2",
    ):
        self.panel_result = panel_result
        self.inverter_result = inverter_result
        self.system_voltage = system_voltage
        self.battery_result = battery_result
        self.inverter_ac_voltage = inverter_ac_voltage

        self.pv_current = pv_current
        self.pv_isc = pv_isc
        self.pv_voc = pv_voc
        self.pv_string_count = pv_string_count

        self.inverter_dc_current = (
            inverter_dc_current
        )

        self.inverter_ac_current = (
            inverter_ac_current
        )

        self.dc_spd_type = dc_spd_type
        self.ac_spd_type = ac_spd_type

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    def calculate(self) -> Dict[str, Any]:
        """
        Perform complete protection engineering.
        """

        inputs = normalize_protection_inputs(
            panel_result=self.panel_result,
            inverter_result=self.inverter_result,
            system_voltage=self.system_voltage,
            battery_result=self.battery_result,
            inverter_ac_voltage=self.inverter_ac_voltage,
            pv_current=self.pv_current,
            pv_isc=self.pv_isc,
            pv_voc=self.pv_voc,
            pv_string_count=self.pv_string_count,
            inverter_dc_current=self.inverter_dc_current,
            inverter_ac_current=self.inverter_ac_current,
        )

        validation = self._validate_inputs(
            inputs
        )

        if not validation["success"]:

            return self._failure_result(
                inputs=inputs,
                warnings=validation["warnings"],
                message=validation["message"],
            )

        # --------------------------------------------------------------
        # PV FUSE
        # --------------------------------------------------------------

        pv_fuse_result = calculate_pv_fuse(
            string_isc=inputs["pv_isc"],
            parallel_strings=inputs[
                "pv_string_count"
            ],
        )

        # --------------------------------------------------------------
        # BATTERY BREAKER
        # --------------------------------------------------------------

        battery_breaker_result = (
            calculate_battery_breaker(
                dc_current=inputs[
                    "inverter_dc_current"
                ],
                battery_voltage=inputs[
                    "actual_battery_voltage"
                ],
            )
        )

        # --------------------------------------------------------------
        # AC BREAKER
        # --------------------------------------------------------------

        ac_breaker_result = calculate_ac_breaker(
            ac_current=inputs[
                "inverter_ac_current"
            ],
            ac_voltage=inputs[
                "inverter_ac_voltage"
            ],
        )

        # --------------------------------------------------------------
        # PV ISOLATOR
        # --------------------------------------------------------------

        pv_isolator_result = (
            calculate_pv_isolator(
                pv_current=inputs[
                    "pv_current"
                ],
                pv_voltage=inputs[
                    "pv_voc"
                ],
            )
        )

        # --------------------------------------------------------------
        # AC ISOLATOR
        # --------------------------------------------------------------

        ac_isolator_result = (
            calculate_ac_isolator(
                ac_current=inputs[
                    "inverter_ac_current"
                ],
                ac_voltage=inputs[
                    "inverter_ac_voltage"
                ],
            )
        )

        # --------------------------------------------------------------
        # DC SPD
        # --------------------------------------------------------------

        dc_spd_result = calculate_dc_spd(
            pv_voltage=inputs[
                "pv_voc"
            ],
            spd_type=self.dc_spd_type,
        )

        # --------------------------------------------------------------
        # AC SPD
        # --------------------------------------------------------------

        ac_spd_result = calculate_ac_spd(
            ac_voltage=inputs[
                "inverter_ac_voltage"
            ],
            spd_type=self.ac_spd_type,
        )

        devices = {
            "pv_fuse": pv_fuse_result,
            "battery_breaker": battery_breaker_result,
            "ac_breaker": ac_breaker_result,
            "pv_isolator": pv_isolator_result,
            "ac_isolator": ac_isolator_result,
            "dc_spd": dc_spd_result,
            "ac_spd": ac_spd_result,
        }

        warnings = []
        messages = []

        for device_name, result in devices.items():

            warnings.extend(
                result.get(
                    "warnings",
                    [],
                )
            )

            if result.get(
                "message"
            ):
                messages.append(
                    f"{device_name}: "
                    f"{result['message']}"
                )

        # --------------------------------------------------------------
        # ADDITIONAL ENGINEERING WARNINGS
        # --------------------------------------------------------------

        warnings.extend(
            self._generate_system_warnings(
                inputs
            )
        )

        success = all(
            result.get(
                "success",
                False,
            )
            for result in devices.values()
        )

        # --------------------------------------------------------------
        # REQUIRED SUMMARY
        # --------------------------------------------------------------

        required = {
            "pv": {
                "operating_current_a": output_number(
                    inputs["pv_current"]
                ),
                "short_circuit_current_a": output_number(
                    inputs["pv_isc"]
                ),
                "corrected_voc_v": output_number(
                    inputs["pv_voc"]
                ),
                "parallel_strings": inputs[
                    "pv_string_count"
                ],
            },
            "battery": {
                "system_voltage_v": output_number(
                    inputs["system_voltage"]
                ),
                "actual_bank_voltage_v": output_number(
                    inputs[
                        "actual_battery_voltage"
                    ]
                ),
                "dc_current_a": output_number(
                    inputs[
                        "inverter_dc_current"
                    ]
                ),
            },
            "inverter_ac": {
                "output_current_a": output_number(
                    inputs[
                        "inverter_ac_current"
                    ]
                ),
                "voltage_v": output_number(
                    inputs[
                        "inverter_ac_voltage"
                    ]
                ),
            },
        }

        # --------------------------------------------------------------
        # SELECTED SUMMARY
        # --------------------------------------------------------------

        selected = {
            "pv_fuse": (
                pv_fuse_result.get(
                    "selected"
                )
            ),
            "battery_breaker": (
                battery_breaker_result.get(
                    "selected"
                )
            ),
            "ac_breaker": (
                ac_breaker_result.get(
                    "selected"
                )
            ),
            "pv_isolator": (
                pv_isolator_result.get(
                    "selected"
                )
            ),
            "ac_isolator": (
                ac_isolator_result.get(
                    "selected"
                )
            ),
            "dc_spd": (
                dc_spd_result.get(
                    "selected"
                )
            ),
            "ac_spd": (
                ac_spd_result.get(
                    "selected"
                )
            ),
        }

        analysis = {
            "pv_operating_current_a": output_number(
                inputs["pv_current"]
            ),
            "pv_short_circuit_current_a": output_number(
                inputs["pv_isc"]
            ),
            "pv_corrected_voc_v": output_number(
                inputs["pv_voc"]
            ),
            "pv_parallel_strings": inputs[
                "pv_string_count"
            ],
            "battery_system_voltage_v": output_number(
                inputs["system_voltage"]
            ),
            "battery_actual_bank_voltage_v": output_number(
                inputs[
                    "actual_battery_voltage"
                ]
            ),
            "battery_dc_current_a": output_number(
                inputs[
                    "inverter_dc_current"
                ]
            ),
            "ac_output_current_a": output_number(
                inputs[
                    "inverter_ac_current"
                ]
            ),
            "ac_voltage_v": output_number(
                inputs[
                    "inverter_ac_voltage"
                ]
            ),
            "pv_protection_required": (
                pv_fuse_result.get(
                    "selected",
                    {}
                ).get(
                    "required",
                    False,
                )
                if isinstance(
                    pv_fuse_result.get(
                        "selected"
                    ),
                    dict,
                )
                else False
            ),
        }

        return {
            "success": success,
            "required": required,
            "selected": selected,
            "devices": devices,
            "analysis": analysis,
            "warnings": warnings,
            "messages": messages,
            "candidates": [],
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "message": (
                "Protection engineering completed successfully."
                if success
                else
                "Protection engineering completed with "
                "one or more unresolved protection requirements."
            ),
        }

    # ==================================================================
    # VALIDATION
    # ==================================================================

    @staticmethod
    def _validate_inputs(
        inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate the minimum electrical inputs required by Phase 8.
        """

        missing = []

        required_values = (
            (
                "PV operating current",
                inputs["pv_current"],
            ),
            (
                "PV short-circuit current",
                inputs["pv_isc"],
            ),
            (
                "PV corrected open-circuit voltage",
                inputs["pv_voc"],
            ),
            (
                "system voltage",
                inputs["system_voltage"],
            ),
            (
                "actual battery-bank voltage",
                inputs["actual_battery_voltage"],
            ),
            (
                "inverter DC current",
                inputs["inverter_dc_current"],
            ),
            (
                "inverter AC output current",
                inputs["inverter_ac_current"],
            ),
        )

        for name, value in required_values:

            if to_decimal(value) <= ZERO:
                missing.append(name)

        if missing:

            return {
                "success": False,
                "warnings": [
                    (
                        "Missing or invalid engineering input(s): "
                        + ", ".join(missing)
                    )
                ],
                "message": (
                    "Phase 8 requires valid electrical values "
                    "from the preceding engineering phases."
                ),
            }

        return {
            "success": True,
            "warnings": [],
            "message": "",
        }

    # ==================================================================
    # SYSTEM WARNINGS
    # ==================================================================

    @staticmethod
    def _generate_system_warnings(
        inputs: Dict[str, Any],
    ) -> List[str]:
        """
        Generate cross-device engineering warnings.
        """

        warnings = []

        # --------------------------------------------------------------
        # PV STRING COUNT
        # --------------------------------------------------------------

        if inputs["pv_string_count"] <= 0:

            warnings.append(
                "PV parallel-string count was not supplied. "
                "PV string protection has therefore been "
                "calculated conservatively from the available "
                "PV current data."
            )

        # --------------------------------------------------------------
        # HIGH PV VOLTAGE
        # --------------------------------------------------------------

        if inputs["pv_voc"] > Decimal("600"):

            warnings.append(
                "PV corrected open-circuit voltage exceeds "
                "600 V DC. Verify the complete DC protection "
                "architecture, equipment ratings, clearances "
                "and installation category."
            )

        # --------------------------------------------------------------
        # HIGH BATTERY VOLTAGE
        # --------------------------------------------------------------

        if inputs[
            "actual_battery_voltage"
        ] > Decimal("60"):

            warnings.append(
                "Battery bank voltage exceeds 60 V DC. "
                "DC shock protection, isolation, insulation, "
                "clearance and creepage requirements require "
                "particular attention."
            )

        # --------------------------------------------------------------
        # LARGE BATTERY CURRENT
        # --------------------------------------------------------------

        if inputs[
            "inverter_dc_current"
        ] > Decimal("200"):

            warnings.append(
                "Battery-side DC current exceeds 200 A. "
                "Verify battery short-circuit current, breaker "
                "interrupting capacity, busbar rating and "
                "parallel battery-string protection."
            )

        # --------------------------------------------------------------
        # LARGE AC CURRENT
        # --------------------------------------------------------------

        if inputs[
            "inverter_ac_current"
        ] > Decimal("100"):

            warnings.append(
                "AC output current exceeds 100 A. "
                "Verify switchgear breaking capacity, cable "
                "ampacity, coordination and distribution-board "
                "requirements."
            )

        return warnings

    # ==================================================================
    # FAILURE RESULT
    # ==================================================================

    @staticmethod
    def _failure_result(
        inputs: Dict[str, Any],
        warnings: List[str],
        message: str,
    ) -> Dict[str, Any]:
        """
        Return a standardized failure result.
        """

        return {
            "success": False,
            "required": {
                "pv": {
                    "operating_current_a": output_number(
                        inputs.get(
                            "pv_current",
                            ZERO,
                        )
                    ),
                    "short_circuit_current_a": output_number(
                        inputs.get(
                            "pv_isc",
                            ZERO,
                        )
                    ),
                    "corrected_voc_v": output_number(
                        inputs.get(
                            "pv_voc",
                            ZERO,
                        )
                    ),
                },
                "battery": {
                    "system_voltage_v": output_number(
                        inputs.get(
                            "system_voltage",
                            ZERO,
                        )
                    ),
                    "actual_bank_voltage_v": output_number(
                        inputs.get(
                            "actual_battery_voltage",
                            ZERO,
                        )
                    ),
                },
                "inverter_ac": {
                    "output_current_a": output_number(
                        inputs.get(
                            "inverter_ac_current",
                            ZERO,
                        )
                    ),
                    "voltage_v": output_number(
                        inputs.get(
                            "inverter_ac_voltage",
                            DEFAULT_AC_VOLTAGE,
                        )
                    ),
                },
            },
            "selected": {},
            "devices": {},
            "analysis": {},
            "warnings": warnings,
            "messages": [],
            "candidates": [],
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
            "message": message,
        }


# ======================================================================
# CANONICAL FUNCTION API
# ======================================================================

def calculate_protection(
    panel_result: Optional[Dict[str, Any]] = None,
    inverter_result: Optional[Dict[str, Any]] = None,
    system_voltage: Any = None,
    battery_result: Optional[Dict[str, Any]] = None,
    inverter_ac_voltage: Any = DEFAULT_AC_VOLTAGE,
    *,
    pv_current: Any = None,
    pv_isc: Any = None,
    pv_voc: Any = None,
    pv_string_count: Any = None,
    inverter_dc_current: Any = None,
    inverter_ac_current: Any = None,
    dc_spd_type: str = "type_2",
    ac_spd_type: str = "type_2",
) -> Dict[str, Any]:
    """
    Canonical functional API for Phase 8.

    Preferred usage:

        result = calculate_protection(
            panel_result=panel_result,
            inverter_result=inverter_result,
            system_voltage=system_voltage,
            battery_result=battery_result,
        )

    Explicit engineering values may also be supplied when required.
    """

    engine = ProtectionEngine(
        panel_result=panel_result,
        inverter_result=inverter_result,
        system_voltage=system_voltage,
        battery_result=battery_result,
        inverter_ac_voltage=inverter_ac_voltage,
        pv_current=pv_current,
        pv_isc=pv_isc,
        pv_voc=pv_voc,
        pv_string_count=pv_string_count,
        inverter_dc_current=inverter_dc_current,
        inverter_ac_current=inverter_ac_current,
        dc_spd_type=dc_spd_type,
        ac_spd_type=ac_spd_type,
    )

    return engine.calculate()


# ======================================================================
# PUBLIC COMPATIBILITY HELPERS
# ======================================================================

def pv_fuse(
    array_isc: Any,
    parallel_strings: Any = 1,
) -> Dict[str, Any]:
    """
    Public PV fuse API.

    Compatibility signature:

        pv_fuse(array_isc)

    Preferred:

        pv_fuse(
            array_isc,
            parallel_strings,
        )
    """

    return calculate_pv_fuse(
        string_isc=array_isc,
        parallel_strings=parallel_strings,
    )


def battery_breaker(
    inverter_power: Any,
    system_voltage: Any,
) -> Dict[str, Any]:
    """
    Compatibility helper.

    The legacy API supplies inverter power and system voltage.

    Phase 8 converts the inverter power into approximate DC current
    using a 95% default inverter efficiency.

    New code should prefer calculate_battery_breaker() with the
    actual inverter DC current supplied by Phase 5.
    """

    power = positive_decimal(
        inverter_power
    )

    voltage = positive_decimal(
        system_voltage
    )

    if power <= ZERO or voltage <= ZERO:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "Inverter power and system voltage are required."
            ],
            "message": (
                "Battery breaker calculation failed."
            ),
        }

    dc_current = (
        power
        /
        (
            voltage
            * Decimal("0.95")
        )
    )

    return calculate_battery_breaker(
        dc_current=dc_current,
        battery_voltage=voltage,
    )


def ac_breaker(
    inverter_power: Any,
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
) -> Dict[str, Any]:
    """
    Compatibility helper.

    Legacy API:

        ac_breaker(inverter_power)

    New code should prefer supplying actual AC output current.
    """

    power = positive_decimal(
        inverter_power
    )

    voltage = positive_decimal(
        ac_voltage,
        default=DEFAULT_AC_VOLTAGE,
    )

    if power <= ZERO:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "warnings": [
                "Inverter power is required."
            ],
            "message": (
                "AC breaker calculation failed."
            ),
        }

    current = (
        power
        / voltage
    )

    return calculate_ac_breaker(
        ac_current=current,
        ac_voltage=voltage,
    )


def select_dc_spd(
    corrected_voc: Any,
    spd_type: str = "type_2",
) -> Dict[str, Any]:
    """
    Public DC SPD API.
    """

    return calculate_dc_spd(
        pv_voltage=corrected_voc,
        spd_type=spd_type,
    )


def select_ac_spd(
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
    spd_type: str = "type_2",
) -> Dict[str, Any]:
    """
    Public AC SPD API.
    """

    return calculate_ac_spd(
        ac_voltage=ac_voltage,
        spd_type=spd_type,
    )


def pv_isolator(
    array_current: Any,
    corrected_voc: Any,
) -> Dict[str, Any]:
    """
    Public PV isolator API.
    """

    return calculate_pv_isolator(
        pv_current=array_current,
        pv_voltage=corrected_voc,
    )


def ac_isolator(
    output_current: Any,
    ac_voltage: Any = DEFAULT_AC_VOLTAGE,
) -> Dict[str, Any]:
    """
    Public AC isolator API.
    """

    return calculate_ac_isolator(
        ac_current=output_current,
        ac_voltage=ac_voltage,
    )


# ======================================================================
# ALIASES
# ======================================================================

select_pv_fuse = calculate_pv_fuse
select_battery_breaker = calculate_battery_breaker
select_ac_breaker = calculate_ac_breaker
select_pv_isolator = calculate_pv_isolator
select_ac_isolator = calculate_ac_isolator
select_pv_dc_spd = calculate_dc_spd