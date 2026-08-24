"""
solar/services/panel_engine.py

PHASE 4
PV / SOLAR ARRAY ENGINE

Responsibilities
---------------

This module performs the complete PV-array engineering calculation.

It is responsible for:

    1. Determining required PV energy.
    2. Determining required PV array power.
    3. Selecting a suitable SolarPanel from the catalogue.
    4. Determining series-panel count.
    5. Determining parallel-string count.
    6. Calculating actual installed PV power.
    7. Calculating array/string voltage.
    8. Calculating array/string current.
    9. Calculating array Voc and Isc.
   10. Ranking alternative panel configurations.
   11. Returning a stable JSON-safe result.

It does NOT:

    - select an inverter
    - select a charge controller
    - select protection
    - size cables
    - calculate pricing beyond panel-array cost
    - modify Django models
    - depend on templates

Design principles
-----------------

All engineering calculations use Decimal.

Database FloatField values are converted to Decimal immediately.

The canonical system voltage comes from Phase 2.

The battery engine does NOT select the PV voltage.

The PV engine does NOT redefine the system voltage.

The charge-controller engine will later validate the PV array against
actual controller voltage/current limits.

SolarPanel model currently contains:

    brand
    model
    power
    vmp
    voc
    imp
    isc
    efficiency
    price
    active

No temperature coefficient is currently stored in the SolarPanel model.
Therefore this engine does NOT invent a temperature coefficient.

A future model can add temperature-coefficient data without changing
the public result contract.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional


# ================================================================
# ENGINE METADATA
# ================================================================

ENGINE_NAME = "PV / Solar Array Engine"
ENGINE_VERSION = "4.0.0"


# ================================================================
# DECIMAL CONSTANTS
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
THOUSAND = Decimal("1000")


# ================================================================
# DEFAULT DESIGN VALUES
# ================================================================

DEFAULT_PEAK_SUN_HOURS = Decimal("5")

DEFAULT_PERFORMANCE_RATIO = Decimal("0.75")

DEFAULT_INVERTER_EFFICIENCY = Decimal("0.95")

DEFAULT_BATTERY_EFFICIENCY = Decimal("0.95")

DEFAULT_ARRAY_MARGIN = Decimal("1.10")

DEFAULT_FUTURE_EXPANSION_FACTOR = Decimal("1.00")

# Minimum number of panels in a series string is always one.
MIN_SERIES_COUNT = 1

# Maximum practical series count used by this stage.
#
# This is NOT a controller maximum.
# It simply prevents nonsensical configurations.
MAX_SERIES_COUNT = 30

# Voltage-class multiplier used when determining a sensible
# operating-voltage target for the PV array.
#
# The array operating voltage should be materially above the
# battery/system voltage because the MPPT must have headroom.
ARRAY_VOLTAGE_MIN_MULTIPLIER = Decimal("2.0")
ARRAY_VOLTAGE_MAX_MULTIPLIER = Decimal("5.0")

# Minimum useful Vmp ratio.
ARRAY_VMP_TARGET_MULTIPLIER = Decimal("3.0")


# ================================================================
# SAFE DECIMAL CONVERSION
# ================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert numeric-like input to Decimal safely.

    Floats are converted through str() so binary floating-point
    artefacts do not enter engineering calculations.
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


def positive(
    value: Any,
    default: Decimal = ZERO,
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


def non_negative(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a Decimal clamped at zero.
    """

    result = to_decimal(
        value,
        default,
    )

    if result < ZERO:
        return ZERO

    return result


def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Consistent Decimal rounding.
    """

    number = to_decimal(
        value
    )

    quantum = Decimal("1").scaleb(
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
    Convert Decimal to JSON-safe int/float.
    """

    number = round_decimal(
        value,
        places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


def ceil_decimal(
    value: Decimal,
) -> int:
    """
    Decimal ceiling to integer.
    """

    if value <= ZERO:
        return 0

    return int(
        value.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


# ================================================================
# PERCENTAGE / FACTOR NORMALIZATION
# ================================================================

def normalize_factor(
    value: Any,
    default: Decimal,
) -> Decimal:
    """
    Normalize a factor.

    Examples:

        0.75 -> 0.75
        75   -> 0.75
        1.10 -> 1.10
        110  -> 1.10
    """

    result = to_decimal(
        value,
        default,
    )

    if result <= ZERO:
        return default

    if result > HUNDRED:
        result = result / HUNDRED

    # A performance ratio cannot exceed 1.
    if result > ONE and default <= ONE:
        result = ONE

    return result


# ================================================================
# SYSTEM VOLTAGE EXTRACTION
# ================================================================

def extract_system_voltage(
    voltage_result: Dict[str, Any],
) -> Decimal:
    """
    Extract canonical system voltage from Phase 2.

    Preferred key:

        system_voltage

    Compatibility aliases are accepted so saved legacy results
    do not immediately break.
    """

    if not isinstance(
        voltage_result,
        dict,
    ):
        return ZERO

    candidates = [
        voltage_result.get(
            "system_voltage"
        ),
        voltage_result.get(
            "recommended_system_voltage"
        ),
        voltage_result.get(
            "selected_voltage"
        ),
    ]

    selected = voltage_result.get(
        "selected"
    )

    if isinstance(
        selected,
        dict,
    ):
        candidates.extend(
            [
                selected.get(
                    "system_voltage"
                ),
                selected.get(
                    "voltage"
                ),
            ]
        )

    for candidate in candidates:

        voltage = to_decimal(
            candidate
        )

        if voltage > ZERO:
            return voltage

    return ZERO


# ================================================================
# DAILY ENERGY EXTRACTION
# ================================================================
def extract_daily_energy(
    load_result: Dict[str, Any],
) -> Decimal:
    """
    Extract daily energy requirement from Phase 1.
    """

    if not isinstance(load_result, dict):
        return ZERO

    # Phase 1 canonical result
    calculations = load_result.get("calculations")

    if isinstance(calculations, dict):
        value = non_negative(
            calculations.get("daily_energy_wh")
        )

        if value > ZERO:
            return value

    # Phase 1 selected result
    selected = load_result.get("selected")

    if isinstance(selected, dict):
        value = non_negative(
            selected.get("daily_energy_wh")
        )

        if value > ZERO:
            return value

    # Compatibility with flat/legacy results
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

    return ZERO
# ================================================================
# LOAD / BATTERY ENERGY EXTRACTION
# ================================================================

def extract_inverter_efficiency(
    load_result: Dict[str, Any],
    battery_result: Optional[Dict[str, Any]] = None,
    inverter_efficiency: Any = None,
) -> Decimal:
    """
    Determine inverter efficiency.

    Priority:

        explicit function argument
        battery-result required/inverter efficiency
        load-result inverter efficiency
        default
    """

    if inverter_efficiency is not None:

        result = normalize_factor(
            inverter_efficiency,
            DEFAULT_INVERTER_EFFICIENCY,
        )

        if result > ZERO:
            return result

    if isinstance(
        battery_result,
        dict,
    ):

        required = battery_result.get(
            "required",
            {},
        )

        if isinstance(
            required,
            dict,
        ):

            result = normalize_factor(
                required.get(
                    "inverter_efficiency"
                ),
                DEFAULT_INVERTER_EFFICIENCY,
            )

            if result > ZERO:
                return result

    if isinstance(
        load_result,
        dict,
    ):

        result = normalize_factor(
            load_result.get(
                "inverter_efficiency"
            ),
            DEFAULT_INVERTER_EFFICIENCY,
        )

        if result > ZERO:
            return result

    return DEFAULT_INVERTER_EFFICIENCY


def extract_battery_efficiency(
    battery_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract battery efficiency from Phase 3.

    This is used only when battery charging losses need to be
    included in PV energy sizing.
    """

    if not isinstance(
        battery_result,
        dict,
    ):
        return DEFAULT_BATTERY_EFFICIENCY

    selected = battery_result.get(
        "selected",
        {},
    )

    if isinstance(
        selected,
        dict,
    ):

        battery = selected.get(
            "battery",
            {},
        )

        if isinstance(
            battery,
            dict,
        ):

            efficiency = normalize_factor(
                battery.get(
                    "efficiency"
                ),
                DEFAULT_BATTERY_EFFICIENCY,
            )

            if efficiency > ZERO:
                return efficiency

    required = battery_result.get(
        "required",
        {},
    )

    if isinstance(
        required,
        dict,
    ):

        efficiency = normalize_factor(
            required.get(
                "battery_efficiency"
            ),
            DEFAULT_BATTERY_EFFICIENCY,
        )

        if efficiency > ZERO:
            return efficiency

    return DEFAULT_BATTERY_EFFICIENCY


# ================================================================
# PV ENERGY REQUIREMENT
# ================================================================

def calculate_required_pv_energy(
    daily_energy_wh: Any,
    inverter_efficiency: Any = DEFAULT_INVERTER_EFFICIENCY,
    battery_efficiency: Any = DEFAULT_BATTERY_EFFICIENCY,
    future_expansion_factor: Any = DEFAULT_FUTURE_EXPANSION_FACTOR,
) -> Dict[str, Decimal]:
    """
    Calculate the energy that the PV system needs to provide.

    Starting point:

        daily AC load energy

    Account for:

        inverter losses
        battery losses

    Then optionally apply future expansion.

    Formula:

        PV energy
        =
        AC energy
        /
        inverter efficiency
        /
        battery efficiency
        ×
        expansion factor

    This prevents the old problem where an arbitrary second
    oversized PV calculation could accidentally double the array.
    """

    daily_energy = non_negative(
        daily_energy_wh
    )

    inverter_eff = normalize_factor(
        inverter_efficiency,
        DEFAULT_INVERTER_EFFICIENCY,
    )

    battery_eff = normalize_factor(
        battery_efficiency,
        DEFAULT_BATTERY_EFFICIENCY,
    )

    expansion = to_decimal(
        future_expansion_factor,
        DEFAULT_FUTURE_EXPANSION_FACTOR,
    )

    if expansion <= ZERO:
        expansion = ONE

    if expansion > Decimal("3"):
        expansion = Decimal("3")

    if daily_energy <= ZERO:
        return {
            "daily_energy_wh": ZERO,
            "inverter_efficiency": inverter_eff,
            "battery_efficiency": battery_eff,
            "future_expansion_factor": expansion,
            "pv_energy_before_expansion_wh": ZERO,
            "required_pv_energy_wh": ZERO,
        }

    pv_energy_before_expansion = (
        daily_energy
        /
        inverter_eff
        /
        battery_eff
    )

    required_pv_energy = (
        pv_energy_before_expansion
        * expansion
    )

    return {
        "daily_energy_wh": daily_energy,

        "inverter_efficiency": inverter_eff,

        "battery_efficiency": battery_eff,

        "future_expansion_factor": expansion,

        "pv_energy_before_expansion_wh": (
            pv_energy_before_expansion
        ),

        "required_pv_energy_wh": (
            required_pv_energy
        ),
    }


# ================================================================
# REQUIRED PV ARRAY POWER
# ================================================================

def calculate_required_array_power(
    required_pv_energy_wh: Any,
    peak_sun_hours: Any = DEFAULT_PEAK_SUN_HOURS,
    performance_ratio: Any = DEFAULT_PERFORMANCE_RATIO,
) -> Dict[str, Decimal]:
    """
    Calculate minimum required PV array power.

    Formula:

        PV power =
        required PV energy
        /
        (peak sun hours × performance ratio)
    """

    energy = non_negative(
        required_pv_energy_wh
    )

    psh = positive(
        peak_sun_hours,
        DEFAULT_PEAK_SUN_HOURS,
    )

    pr = normalize_factor(
        performance_ratio,
        DEFAULT_PERFORMANCE_RATIO,
    )

    denominator = (
        psh
        * pr
    )

    if denominator <= ZERO:
        return {
            "peak_sun_hours": psh,
            "performance_ratio": pr,
            "required_array_power_w": ZERO,
        }

    required_power = (
        energy
        /
        denominator
    )

    return {
        "peak_sun_hours": psh,

        "performance_ratio": pr,

        "required_array_power_w": (
            required_power
        ),
    }


# ================================================================
# ARRAY VOLTAGE TARGET
# ================================================================

def calculate_array_voltage_target(
    system_voltage: Any,
) -> Dict[str, Decimal]:
    """
    Establish an engineering target for PV operating voltage.

    This is NOT an MPPT controller limit.

    It is simply a design target ensuring the PV array has
    meaningful voltage headroom above the battery/system voltage.

    For common systems this gives approximately:

        12 V class -> 36 V target
        24 V class -> 72 V target
        48 V class -> 144 V target
        96 V class -> 288 V target

    The actual panel/string configuration is determined from the
    selected panel's Vmp and Voc.
    """

    system = positive(
        system_voltage
    )

    if system <= ZERO:
        return {
            "minimum_array_voltage": ZERO,
            "target_array_voltage": ZERO,
            "maximum_array_voltage": ZERO,
        }

    minimum_voltage = (
        system
        * ARRAY_VOLTAGE_MIN_MULTIPLIER
    )

    target_voltage = (
        system
        * ARRAY_VMP_TARGET_MULTIPLIER
    )

    maximum_voltage = (
        system
        * ARRAY_VOLTAGE_MAX_MULTIPLIER
    )

    return {
        "minimum_array_voltage": minimum_voltage,

        "target_array_voltage": target_voltage,

        "maximum_array_voltage": maximum_voltage,
    }


# ================================================================
# PANEL NORMALIZATION
# ================================================================

def normalize_panel_record(
    panel: Any,
) -> Dict[str, Any]:
    """
    Normalize Django SolarPanel or dictionary into one internal
    representation.
    """

    if isinstance(
        panel,
        dict,
    ):

        getter = panel.get

    else:

        getter = lambda key, default=None: getattr(
            panel,
            key,
            default,
        )

    return {
        "id": getter(
            "id"
        ),

        "brand": str(
            getter(
                "brand",
                "",
            )
            or ""
        ),

        "model": str(
            getter(
                "model",
                "",
            )
            or ""
        ),

        "power": to_decimal(
            getter(
                "power",
                0,
            )
        ),

        "vmp": to_decimal(
            getter(
                "vmp",
                0,
            )
        ),

        "voc": to_decimal(
            getter(
                "voc",
                0,
            )
        ),

        "imp": to_decimal(
            getter(
                "imp",
                0,
            )
        ),

        "isc": to_decimal(
            getter(
                "isc",
                0,
            )
        ),

        "efficiency": normalize_factor(
            getter(
                "efficiency",
                Decimal("0.21"),
            ),
            Decimal("0.21"),
        ),

        "price": to_decimal(
            getter(
                "price",
                0,
            )
        ),

        "active": bool(
            getter(
                "active",
                True,
            )
        ),
    }


# ================================================================
# PANEL VALIDATION
# ================================================================

def validate_panel(
    panel: Dict[str, Any],
) -> List[str]:
    """
    Return validation errors for a panel.
    """

    errors = []

    if panel[
        "power"
    ] <= ZERO:
        errors.append(
            "Panel power must be greater than zero."
        )

    if panel[
        "vmp"
    ] <= ZERO:
        errors.append(
            "Panel Vmp must be greater than zero."
        )

    if panel[
        "voc"
    ] <= ZERO:
        errors.append(
            "Panel Voc must be greater than zero."
        )

    if panel[
        "imp"
    ] <= ZERO:
        errors.append(
            "Panel Imp must be greater than zero."
        )

    if panel[
        "isc"
    ] <= ZERO:
        errors.append(
            "Panel Isc must be greater than zero."
        )

    if (
        panel["voc"] <= panel["vmp"]
    ):
        errors.append(
            "Panel Voc must be greater than Vmp."
        )

    if (
        panel["isc"] <= panel["imp"]
    ):
        errors.append(
            "Panel Isc should be greater than Imp."
        )

    return errors


# ================================================================
# SERIES COUNT
# ================================================================

def determine_series_count(
    panel: Dict[str, Any],
    target_voltage: Decimal,
    minimum_voltage: Decimal,
    maximum_voltage: Decimal,
) -> Dict[str, Any]:
    """
    Determine the best series-panel count.

    The primary target is Vmp.

    The algorithm considers the target operating voltage and
    rejects configurations whose nominal Voc already exceeds the
    engineering maximum.

    Exact MPPT controller limits are deliberately checked later
    by the controller engine.
    """

    vmp = panel[
        "vmp"
    ]

    voc = panel[
        "voc"
    ]

    if vmp <= ZERO or voc <= ZERO:

        return {
            "success": False,
            "series_count": 0,
            "reason": (
                "Panel voltage data is invalid."
            ),
        }

    ideal_series = ceil_decimal(
        target_voltage
        /
        vmp
    )

    candidate_counts = set()

    for count in range(
        max(
            MIN_SERIES_COUNT,
            ideal_series - 2,
        ),
        min(
            MAX_SERIES_COUNT,
            ideal_series + 3,
        )
        + 1,
    ):

        candidate_counts.add(
            count
        )

    # Always include the minimum count required to enter the
    # engineering voltage window.
    minimum_series = max(
        1,
        ceil_decimal(
            minimum_voltage
            /
            vmp
        ),
    )

    candidate_counts.add(
        minimum_series
    )

    valid = []

    for series in sorted(
        candidate_counts
    ):

        string_vmp = (
            vmp
            * Decimal(series)
        )

        string_voc = (
            voc
            * Decimal(series)
        )

        # A string must reach the minimum operating-voltage
        # target.
        if string_vmp < minimum_voltage:
            continue

        # Never deliberately exceed the engineering maximum
        # Voc target.
        if string_voc > maximum_voltage:
            continue

        voltage_error = abs(
            string_vmp
            -
            target_voltage
        )

        valid.append(
            {
                "series_count": series,
                "string_vmp": string_vmp,
                "string_voc": string_voc,
                "voltage_error": voltage_error,
            }
        )

    if not valid:

        # There may be no configuration inside the generic
        # engineering window. We still calculate a sensible
        # minimum series configuration, but mark it for later
        # controller verification.
        fallback_series = max(
            1,
            ideal_series,
        )

        string_vmp = (
            vmp
            * Decimal(fallback_series)
        )

        string_voc = (
            voc
            * Decimal(fallback_series)
        )

        return {
            "success": True,
            "series_count": fallback_series,
            "string_vmp": string_vmp,
            "string_voc": string_voc,
            "requires_controller_verification": True,
            "reason": (
                "No series configuration fell completely inside "
                "the generic PV voltage window. The closest "
                "configuration was retained and must be checked "
                "against the actual MPPT controller."
            ),
        }

    valid.sort(
        key=lambda item: (
            item["voltage_error"],
            item["series_count"],
        )
    )

    best = valid[0]

    return {
        "success": True,
        "series_count": best[
            "series_count"
        ],
        "string_vmp": best[
            "string_vmp"
        ],
        "string_voc": best[
            "string_voc"
        ],
        "requires_controller_verification": False,
        "reason": (
            "Series configuration selected to place PV "
            "operating voltage near the engineering target."
        ),
    }


# ================================================================
# ARRAY CONFIGURATION
# ================================================================

def calculate_array_configuration(
    panel: Dict[str, Any],
    required_array_power: Decimal,
    system_voltage: Decimal,
) -> Dict[str, Any]:
    """
    Calculate the complete series/parallel configuration for a
    particular panel.

    Important electrical rules:

        Series:
            voltage increases
            current remains approximately the same

        Parallel:
            current increases
            voltage remains approximately the same
    """

    voltage_target = (
        calculate_array_voltage_target(
            system_voltage
        )
    )

    series_result = (
        determine_series_count(
            panel=panel,
            target_voltage=(
                voltage_target[
                    "target_array_voltage"
                ]
            ),
            minimum_voltage=(
                voltage_target[
                    "minimum_array_voltage"
                ]
            ),
            maximum_voltage=(
                voltage_target[
                    "maximum_array_voltage"
                ]
            ),
        )
    )

    if not series_result[
        "success"
    ]:

        return {
            "success": False,
            "message": series_result[
                "reason"
            ],
        }

    series = int(
        series_result[
            "series_count"
        ]
    )

    panel_power = panel[
        "power"
    ]

    if panel_power <= ZERO:

        return {
            "success": False,
            "message": (
                "Panel power must be greater than zero."
            ),
        }

    # Number of panels required purely from power.
    minimum_panel_quantity = max(
        1,
        ceil_decimal(
            required_array_power
            /
            panel_power
        ),
    )

    # Parallel strings must contain whole series strings.
    parallel = max(
        1,
        ceil_decimal(
            Decimal(
                minimum_panel_quantity
            )
            /
            Decimal(series)
        ),
    )

    total_quantity = (
        series
        * parallel
    )

    # ------------------------------------------------------------
    # ACTUAL ARRAY VALUES
    # ------------------------------------------------------------

    array_power = (
        panel_power
        * Decimal(total_quantity)
    )

    string_vmp = (
        panel[
            "vmp"
        ]
        * Decimal(series)
    )

    string_voc = (
        panel[
            "voc"
        ]
        * Decimal(series)
    )

    string_imp = panel[
        "imp"
    ]

    string_isc = panel[
        "isc"
    ]

    array_current_imp = (
        string_imp
        * Decimal(parallel)
    )

    array_current_isc = (
        string_isc
        * Decimal(parallel)
    )

    # ------------------------------------------------------------
    # ARRAY MARGIN
    # ------------------------------------------------------------

    power_margin = (
        array_power
        -
        required_array_power
    )

    power_margin_percent = (
        power_margin
        /
        required_array_power
        *
        HUNDRED
        if required_array_power > ZERO
        else ZERO
    )

    return {
        "success": True,

        "series_count": series,

        "parallel_count": parallel,

        "total_quantity": total_quantity,

        "installed_power_w": array_power,

        "string_vmp": string_vmp,

        "string_voc": string_voc,

        "array_vmp": string_vmp,

        "array_voltage": string_vmp,

        "corrected_voc": string_voc,

        "string_imp": string_imp,

        "string_isc": string_isc,

        "array_imp": array_current_imp,

        "array_current": array_current_imp,

        "array_isc": array_current_isc,

        "required_array_power_w": (
            required_array_power
        ),

        "power_margin_w": power_margin,

        "power_margin_percent": (
            power_margin_percent
        ),

        "minimum_panel_quantity": (
            minimum_panel_quantity
        ),

        "minimum_array_voltage": (
            voltage_target[
                "minimum_array_voltage"
            ]
        ),

        "target_array_voltage": (
            voltage_target[
                "target_array_voltage"
            ]
        ),

        "maximum_array_voltage": (
            voltage_target[
                "maximum_array_voltage"
            ]
        ),

        "requires_controller_verification": (
            series_result.get(
                "requires_controller_verification",
                False,
            )
        ),

        "series_reason": series_result[
            "reason"
        ],
    }


# ================================================================
# PANEL CANDIDATE EVALUATION
# ================================================================

def evaluate_panel_candidate(
    panel: Any,
    required_array_power: Any,
    system_voltage: Any,
) -> Dict[str, Any]:
    """
    Evaluate one panel model.
    """

    record = normalize_panel_record(
        panel
    )

    validation_errors = validate_panel(
        record
    )

    if validation_errors:

        return {
            "compatible": False,

            "status": "invalid_panel_data",

            "reason": (
                " ".join(
                    validation_errors
                )
            ),

            "panel": record,

            "score": ZERO,
        }

    required_power = positive(
        required_array_power
    )

    system = positive(
        system_voltage
    )

    if required_power <= ZERO:

        return {
            "compatible": False,
            "status": "invalid_requirement",
            "reason": (
                "Required PV array power must be greater than zero."
            ),
            "panel": record,
            "score": ZERO,
        }

    if system <= ZERO:

        return {
            "compatible": False,
            "status": "invalid_system_voltage",
            "reason": (
                "System voltage must be greater than zero."
            ),
            "panel": record,
            "score": ZERO,
        }

    configuration = (
        calculate_array_configuration(
            panel=record,
            required_array_power=required_power,
            system_voltage=system,
        )
    )

    if not configuration[
        "success"
    ]:

        return {
            "compatible": False,

            "status": "configuration_failed",

            "reason": configuration[
                "message"
            ],

            "panel": record,

            "score": ZERO,
        }

    installed_power = configuration[
        "installed_power_w"
    ]

    oversize = (
        installed_power
        -
        required_power
    )

    oversize_percent = (
        oversize
        /
        required_power
        *
        HUNDRED
    )

    total_quantity = configuration[
        "total_quantity"
    ]

    # ------------------------------------------------------------
    # PANEL SCORE
    # ------------------------------------------------------------

    score = calculate_panel_score(
        panel=record,
        total_quantity=total_quantity,
        oversize_percent=oversize_percent,
        installed_power=installed_power,
        required_power=required_power,
    )

    return {
        "compatible": True,

        "status": "compatible",

        "reason": (
            "Panel can form a complete PV array "
            "satisfying the required PV power."
        ),

        "panel": record,

        "series_count": configuration[
            "series_count"
        ],

        "parallel_count": configuration[
            "parallel_count"
        ],

        "total_quantity": total_quantity,

        "installed_power_w": installed_power,

        "required_array_power_w": required_power,

        "oversize_w": oversize,

        "oversize_percent": oversize_percent,

        "string_vmp": configuration[
            "string_vmp"
        ],

        "string_voc": configuration[
            "string_voc"
        ],

        "array_voltage": configuration[
            "array_voltage"
        ],

        "corrected_voc": configuration[
            "corrected_voc"
        ],

        "string_imp": configuration[
            "string_imp"
        ],

        "string_isc": configuration[
            "string_isc"
        ],

        "array_current": configuration[
            "array_current"
        ],

        "array_imp": configuration[
            "array_imp"
        ],

        "array_isc": configuration[
            "array_isc"
        ],

        "minimum_panel_quantity": configuration[
            "minimum_panel_quantity"
        ],

        "minimum_array_voltage": configuration[
            "minimum_array_voltage"
        ],

        "target_array_voltage": configuration[
            "target_array_voltage"
        ],

        "maximum_array_voltage": configuration[
            "maximum_array_voltage"
        ],

        "requires_controller_verification": (
            configuration[
                "requires_controller_verification"
            ]
        ),

        "series_reason": configuration[
            "series_reason"
        ],

        "total_price": (
            record[
                "price"
            ]
            *
            Decimal(total_quantity)
        ),

        "score": score,
    }


# ================================================================
# PANEL SCORE
# ================================================================

def calculate_panel_score(
    panel: Dict[str, Any],
    total_quantity: int,
    oversize_percent: Decimal,
    installed_power: Decimal,
    required_power: Decimal,
) -> Decimal:
    """
    Rank panel configurations.

    Lower unnecessary oversizing and fewer panels are preferred,
    but the scoring does not blindly select the cheapest panel.

    Electrical suitability remains the primary requirement.
    """

    score = Decimal("100")

    # ------------------------------------------------------------
    # Panel quantity
    # ------------------------------------------------------------

    if total_quantity <= 4:
        score += Decimal("15")

    elif total_quantity <= 8:
        score += Decimal("12")

    elif total_quantity <= 12:
        score += Decimal("10")

    elif total_quantity <= 20:
        score += Decimal("6")

    else:
        score -= Decimal("2")

    # ------------------------------------------------------------
    # Oversizing
    # ------------------------------------------------------------

    if oversize_percent <= Decimal("10"):
        score += Decimal("25")

    elif oversize_percent <= Decimal("20"):
        score += Decimal("20")

    elif oversize_percent <= Decimal("30"):
        score += Decimal("12")

    elif oversize_percent <= Decimal("50"):
        score += Decimal("4")

    else:
        score -= Decimal("10")

    # ------------------------------------------------------------
    # Panel efficiency
    # ------------------------------------------------------------

    efficiency = panel[
        "efficiency"
    ]

    if efficiency >= Decimal("0.22"):
        score += Decimal("10")

    elif efficiency >= Decimal("0.20"):
        score += Decimal("7")

    elif efficiency >= Decimal("0.18"):
        score += Decimal("4")

    # ------------------------------------------------------------
    # Power density / panel size
    # ------------------------------------------------------------

    if panel[
        "power"
    ] >= Decimal("500"):

        score += Decimal("5")

    # ------------------------------------------------------------
    # Electrical quality
    # ------------------------------------------------------------

    if (
        panel[
            "voc"
        ]
        >
        panel[
            "vmp"
        ]
    ):
        score += Decimal("5")

    if (
        panel[
            "isc"
        ]
        >
        panel[
            "imp"
        ]
    ):
        score += Decimal("5")

    return max(
        ZERO,
        score,
    )


# ================================================================
# PANEL SELECTION
# ================================================================

def select_panel(
    candidates: Iterable[Any],
    required_array_power: Any,
    system_voltage: Any,
    preferred_brand: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Select the best SolarPanel from supplied candidates.

    candidates may be:

        Django QuerySet
        list[Model]
        list[dict]
    """

    required_power = positive(
        required_array_power
    )

    system = positive(
        system_voltage
    )

    if required_power <= ZERO:

        return {
            "success": False,
            "selected": {},
            "alternatives": [],
            "quantity": 0,
            "warnings": [
                "Required PV array power must be greater than zero."
            ],
            "message": (
                "PV panel selection cannot proceed."
            ),
        }

    if system <= ZERO:

        return {
            "success": False,
            "selected": {},
            "alternatives": [],
            "quantity": 0,
            "warnings": [
                "System voltage must be greater than zero."
            ],
            "message": (
                "PV panel selection cannot proceed."
            ),
        }

    evaluated = []

    preferred = (
        str(
            preferred_brand
            or ""
        )
        .strip()
        .lower()
    )

    for candidate in candidates:

        record = normalize_panel_record(
            candidate
        )

        if not record[
            "active"
        ]:
            continue

        if (
            preferred
            and preferred != "any"
            and preferred not in record[
                "brand"
            ].lower()
        ):
            continue

        result = evaluate_panel_candidate(
            panel=record,
            required_array_power=(
                required_power
            ),
            system_voltage=system,
        )

        evaluated.append(
            result
        )

    compatible = [
        result
        for result in evaluated
        if result.get(
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

    if not compatible:

        return {
            "success": False,

            "selected": {},

            "alternatives": [],

            "quantity": 0,

            "warnings": [
                "No valid solar-panel configuration "
                "was found in the available catalogue."
            ],

            "message": (
                "PV panel selection failed."
            ),

            "candidates": (
                serialize_candidates(
                    evaluated
                )
            ),
        }

    selected = compatible[
        0
    ]

    alternatives = compatible[
        1:6
    ]

    warnings = []

    if selected[
        "oversize_percent"
    ] > Decimal("30"):

        warnings.append(
            "Selected PV array exceeds the calculated "
            "minimum requirement by more than 30%."
        )

    if selected[
        "requires_controller_verification"
    ]:

        warnings.append(
            "PV string voltage requires verification against "
            "the actual MPPT controller maximum PV voltage."
        )

    if selected[
        "total_quantity"
    ] > 20:

        warnings.append(
            "The selected array contains a large number "
            "of modules. Consider higher-wattage modules "
            "where commercially appropriate."
        )

    return {
        "success": True,

        "selected": serialize_candidate(
            selected
        ),

        "alternatives": [
            serialize_candidate(
                item
            )
            for item in alternatives
        ],

        "quantity": int(
            selected[
                "total_quantity"
            ]
        ),

        "warnings": warnings,

        "message": (
            "PV panel and array configuration selected successfully."
        ),

        "candidates": (
            serialize_candidates(
                evaluated
            )
        ),
    }


# ================================================================
# COMPLETE PHASE 4 ENGINE
# ================================================================

def calculate_pv_array(
    load_result: Dict[str, Any],
    voltage_result: Dict[str, Any],
    battery_result: Optional[Dict[str, Any]],
    panel_candidates: Iterable[Any],
    peak_sun_hours: Any = DEFAULT_PEAK_SUN_HOURS,
    performance_ratio: Any = DEFAULT_PERFORMANCE_RATIO,
    inverter_efficiency: Any = None,
    future_expansion_factor: Any = DEFAULT_FUTURE_EXPANSION_FACTOR,
    preferred_brand: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main Phase 4 public entry point.

    Inputs
    ------

    load_result:
        Complete Phase 1 result.

    voltage_result:
        Complete Phase 2 result.

    battery_result:
        Complete Phase 3 result.

    panel_candidates:
        Active SolarPanel database objects/dictionaries.

    peak_sun_hours:
        User/design-location PSH.

    performance_ratio:
        PV system performance ratio.

    inverter_efficiency:
        Optional explicit inverter efficiency.

    future_expansion_factor:
        Optional future expansion factor.

    preferred_brand:
        Optional brand preference.

    The engine automatically selects the panel and array.
    """

    # ============================================================
    # VALIDATION
    # ============================================================

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

    system_voltage = extract_system_voltage(
        voltage_result
    )

    if system_voltage <= ZERO:

        return failed_result(
            "A valid system voltage from Phase 2 "
            "is required for PV sizing."
        )

    daily_energy = extract_daily_energy(
        load_result
    )

    if daily_energy <= ZERO:

        return failed_result(
            "Daily energy from Phase 1 is required "
            "for PV sizing."
        )

    # ============================================================
    # EFFICIENCIES
    # ============================================================

    inverter_eff = extract_inverter_efficiency(
        load_result=load_result,
        battery_result=battery_result,
        inverter_efficiency=inverter_efficiency,
    )

    battery_eff = extract_battery_efficiency(
        battery_result
    )

    psh = positive(
        peak_sun_hours,
        DEFAULT_PEAK_SUN_HOURS,
    )

    pr = normalize_factor(
        performance_ratio,
        DEFAULT_PERFORMANCE_RATIO,
    )

    expansion = to_decimal(
        future_expansion_factor,
        DEFAULT_FUTURE_EXPANSION_FACTOR,
    )

    if expansion <= ZERO:
        expansion = ONE

    # ============================================================
    # PV ENERGY
    # ============================================================

    energy_result = (
        calculate_required_pv_energy(
            daily_energy_wh=daily_energy,
            inverter_efficiency=inverter_eff,
            battery_efficiency=battery_eff,
            future_expansion_factor=expansion,
        )
    )

    # ============================================================
    # PV POWER
    # ============================================================

    power_result = (
        calculate_required_array_power(
            required_pv_energy_wh=(
                energy_result[
                    "required_pv_energy_wh"
                ]
            ),
            peak_sun_hours=psh,
            performance_ratio=pr,
        )
    )

    required_array_power = power_result[
        "required_array_power_w"
    ]

    if required_array_power <= ZERO:

        return failed_result(
            "Calculated PV array power is zero or invalid."
        )

    # ============================================================
    # PANEL SELECTION
    # ============================================================

    selection = select_panel(
        candidates=panel_candidates,
        required_array_power=(
            required_array_power
        ),
        system_voltage=system_voltage,
        preferred_brand=preferred_brand,
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

                "daily_energy_kwh": output_number(
                    daily_energy
                    / THOUSAND
                ),

                "pv_energy_required_wh": (
                    output_number(
                        energy_result[
                            "required_pv_energy_wh"
                        ]
                    )
                ),

                "pv_energy_required_kwh": (
                    output_number(
                        energy_result[
                            "required_pv_energy_wh"
                        ]
                        / THOUSAND
                    )
                ),

                "required_array_power_w": (
                    output_number(
                        required_array_power
                    )
                ),

                "required_array_power_kw": (
                    output_number(
                        required_array_power
                        / THOUSAND
                    )
                ),

                "peak_sun_hours": output_number(
                    psh
                ),

                "performance_ratio": output_number(
                    pr,
                    places=4,
                ),

                "inverter_efficiency": output_number(
                    inverter_eff,
                    places=4,
                ),

                "battery_efficiency": output_number(
                    battery_eff,
                    places=4,
                ),

                "future_expansion_factor": output_number(
                    expansion,
                    places=4,
                ),
            },

            "selected": {},

            "alternatives": [],

            "candidates": selection.get(
                "candidates",
                [],
            ),

            "warnings": selection.get(
                "warnings",
                [],
            ),

            "messages": [],

            "engine": ENGINE_NAME,

            "engine_version": ENGINE_VERSION,

            "message": selection.get(
                "message",
                "PV selection failed.",
            ),
        }

    selected = selection[
        "selected"
    ]

    # ============================================================
    # WARNINGS
    # ============================================================

    warnings = list(
        selection.get(
            "warnings",
            [],
        )
    )

    if psh < Decimal("4"):
        warnings.append(
            "Peak sun hours are below 4 hours/day. "
            "PV capacity is therefore relatively sensitive "
            "to seasonal solar conditions."
        )

    if psh > Decimal("8"):
        warnings.append(
            "Peak sun hours above 8 are unusually high for "
            "a generic design input. Verify the selected "
            "solar resource."
        )

    if pr < Decimal("0.70"):
        warnings.append(
            "Performance ratio is below 0.70. "
            "The resulting PV array will be significantly larger."
        )

    if selected[
        "array_isc"
    ] > Decimal("100"):

        warnings.append(
            "PV array Isc is high. Multiple MPPT inputs, "
            "string combiners or multiple controller channels "
            "may be required in the controller/protection stages."
        )

    if selected[
        "total_quantity"
    ] > 30:

        warnings.append(
            "Large PV module count detected."
        )

    # ============================================================
    # MESSAGES
    # ============================================================

    messages = [
        (
            f"PV energy requirement calculated from "
            f"{output_number(daily_energy)} Wh/day."
        ),
        (
            f"Required minimum PV array power: "
            f"{output_number(required_array_power)} W."
        ),
        (
            f"Selected array: "
            f"{selected['total_quantity']} × "
            f"{selected['panel']['power']} W."
        ),
        (
            f"Array configuration: "
            f"{selected['series_count']}S"
            f"{selected['parallel_count']}P."
        ),
    ]

    # ============================================================
    # FINAL RESULT
    # ============================================================

    return {
        "success": True,

        "system_voltage": output_number(
            system_voltage
        ),

        # --------------------------------------------------------
        # REQUIRED
        # --------------------------------------------------------

        "required": {
            "daily_energy_wh": output_number(
                daily_energy
            ),

            "daily_energy_kwh": output_number(
                daily_energy
                / THOUSAND
            ),

            "pv_energy_required_wh": output_number(
                energy_result[
                    "required_pv_energy_wh"
                ]
            ),

            "pv_energy_required_kwh": output_number(
                energy_result[
                    "required_pv_energy_wh"
                ]
                / THOUSAND
            ),

            "required_array_power_w": output_number(
                required_array_power
            ),

            "required_array_power_kw": output_number(
                required_array_power
                / THOUSAND
            ),

            "peak_sun_hours": output_number(
                psh
            ),

            "performance_ratio": output_number(
                pr,
                places=4,
            ),

            "inverter_efficiency": output_number(
                inverter_eff,
                places=4,
            ),

            "battery_efficiency": output_number(
                battery_eff,
                places=4,
            ),

            "future_expansion_factor": output_number(
                expansion,
                places=4,
            ),

            "minimum_array_voltage": output_number(
                selected[
                    "minimum_array_voltage"
                ]
            ),

            "target_array_voltage": output_number(
                selected[
                    "target_array_voltage"
                ]
            ),

            "maximum_array_voltage": output_number(
                selected[
                    "maximum_array_voltage"
                ]
            ),
        },

        # --------------------------------------------------------
        # SELECTED
        # --------------------------------------------------------

        "selected": selected,

        # --------------------------------------------------------
        # ALTERNATIVES
        # --------------------------------------------------------

        "alternatives": selection[
            "alternatives"
        ],

        # --------------------------------------------------------
        # CANDIDATES
        # --------------------------------------------------------

        "candidates": selection.get(
            "candidates",
            [],
        ),

        # --------------------------------------------------------
        # WARNINGS
        # --------------------------------------------------------

        "warnings": warnings,

        # --------------------------------------------------------
        # MESSAGES
        # --------------------------------------------------------

        "messages": messages,

        # --------------------------------------------------------
        # ENGINE
        # --------------------------------------------------------

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        "message": (
            "PV array requirement, panel selection and "
            "series/parallel configuration completed successfully."
        ),
    }


# ================================================================
# SERIALIZATION
# ================================================================

def serialize_panel_record(
    panel: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert panel record to JSON-safe data.
    """

    return {
        "id": panel.get(
            "id"
        ),

        "brand": panel.get(
            "brand",
            "",
        ),

        "model": panel.get(
            "model",
            "",
        ),

        "power": output_number(
            panel.get(
                "power",
                ZERO,
            )
        ),

        "vmp": output_number(
            panel.get(
                "vmp",
                ZERO,
            )
        ),

        "voc": output_number(
            panel.get(
                "voc",
                ZERO,
            )
        ),

        "imp": output_number(
            panel.get(
                "imp",
                ZERO,
            )
        ),

        "isc": output_number(
            panel.get(
                "isc",
                ZERO,
            )
        ),

        "efficiency": output_number(
            panel.get(
                "efficiency",
                ZERO,
            ),
            places=4,
        ),

        "price": output_number(
            panel.get(
                "price",
                ZERO,
            )
        ),

        "active": bool(
            panel.get(
                "active",
                True,
            )
        ),
    }


def serialize_candidate(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Serialize one complete evaluated panel configuration.
    """

    return {
        "compatible": bool(
            result.get(
                "compatible",
                False,
            )
        ),

        "status": result.get(
            "status",
            "",
        ),

        "reason": result.get(
            "reason",
            "",
        ),

        "panel": serialize_panel_record(
            result.get(
                "panel",
                {},
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

        "installed_power_w": output_number(
            result.get(
                "installed_power_w",
                ZERO,
            )
        ),

        "installed_power_kw": output_number(
            to_decimal(
                result.get(
                    "installed_power_w",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "required_array_power_w": output_number(
            result.get(
                "required_array_power_w",
                ZERO,
            )
        ),

        "oversize_w": output_number(
            result.get(
                "oversize_w",
                ZERO,
            )
        ),

        "oversize_percent": output_number(
            result.get(
                "oversize_percent",
                ZERO,
            )
        ),

        # --------------------------------------------------------
        # VOLTAGE
        # --------------------------------------------------------

        "string_vmp": output_number(
            result.get(
                "string_vmp",
                ZERO,
            )
        ),

        "string_voc": output_number(
            result.get(
                "string_voc",
                ZERO,
            )
        ),

        "array_voltage": output_number(
            result.get(
                "array_voltage",
                ZERO,
            )
        ),

        "corrected_voc": output_number(
            result.get(
                "corrected_voc",
                ZERO,
            )
        ),

        # --------------------------------------------------------
        # CURRENT
        # --------------------------------------------------------

        "string_imp": output_number(
            result.get(
                "string_imp",
                ZERO,
            )
        ),

        "string_isc": output_number(
            result.get(
                "string_isc",
                ZERO,
            )
        ),

        "array_current": output_number(
            result.get(
                "array_current",
                ZERO,
            )
        ),

        "array_imp": output_number(
            result.get(
                "array_imp",
                ZERO,
            )
        ),

        "array_isc": output_number(
            result.get(
                "array_isc",
                ZERO,
            )
        ),

        # --------------------------------------------------------
        # VOLTAGE TARGETS
        # --------------------------------------------------------

        "minimum_array_voltage": output_number(
            result.get(
                "minimum_array_voltage",
                ZERO,
            )
        ),

        "target_array_voltage": output_number(
            result.get(
                "target_array_voltage",
                ZERO,
            )
        ),

        "maximum_array_voltage": output_number(
            result.get(
                "maximum_array_voltage",
                ZERO,
            )
        ),

        # --------------------------------------------------------
        # CONTROLLER FLAG
        # --------------------------------------------------------

        "requires_controller_verification": bool(
            result.get(
                "requires_controller_verification",
                False,
            )
        ),

        # --------------------------------------------------------
        # PRICE
        # --------------------------------------------------------

        "total_price": output_number(
            result.get(
                "total_price",
                ZERO,
            )
        ),

        # --------------------------------------------------------
        # RANKING
        # --------------------------------------------------------

        "score": output_number(
            result.get(
                "score",
                ZERO,
            )
        ),

        "series_reason": result.get(
            "series_reason",
            "",
        ),
    }


def serialize_candidates(
    results: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Serialize all candidate results.
    """

    return [
        serialize_candidate(
            result
        )
        for result in results
    ]


# ================================================================
# FAILURE CONTRACT
# ================================================================

def failed_result(
    message: str,
) -> Dict[str, Any]:
    """
    Standard Phase 4 failure result.
    """

    return {
        "success": False,

        "system_voltage": None,

        "required": {},

        "selected": {},

        "alternatives": [],

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

calculate_panels = calculate_pv_array

run_panel_engine = calculate_pv_array

select_solar_panel = select_panel