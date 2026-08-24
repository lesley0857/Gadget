"""
solar/services/system_voltage_engine.py

PHASE 2
SYSTEM VOLTAGE ENGINE

This module determines the appropriate DC battery-system voltage
for a solar PV system.

IMPORTANT ENGINEERING DISTINCTIONS
-----------------------------------

1. Battery nominal voltage
   -----------------------
   The manufacturer's nominal voltage of one battery.

   Examples:
       12.0 V
       12.8 V
       24.0 V
       25.6 V
       48.0 V
       51.2 V

2. System voltage
   ---------------
   The nominal DC voltage class of the solar system.

   Examples:
       12 V
       24 V
       48 V
       96 V
       120 V
       192 V
       240 V
       384 V

3. Battery-bank voltage
   --------------------
   The actual nominal voltage created by batteries connected
   in series.

   Example:

       4 × 12.8 V batteries
       = 51.2 V actual bank voltage

       This belongs to the 48 V nominal system class.

The system voltage engine therefore DOES NOT assume that a
battery's individual voltage is equal to the system voltage.
That relationship is handled later by the battery engine.

ENGINE CONTRACT
---------------

INPUT:

    load_result = {
        "load_watts": ...,
        "surge_watts": ...,
        "motor_load": ...,
        "total_motors": ...,
        "simultaneous_start_load": ...,
        ...
    }

OUTPUT:

    {
        "success": True,
        "system_voltage": 48,
        "recommended_system_voltage": 48,
        "minimum_system_voltage": 48,
        "required": {...},
        "analysis": {...},
        "warnings": [...],
        "messages": [...],
        "candidates": [...]
    }

NUMERIC POLICY
--------------

All internal engineering calculations use Decimal.

The final result contains JSON/template-friendly numeric values.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, List, Optional


# ================================================================
# DECIMAL HELPERS
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")


def _decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert a value to Decimal.

    We deliberately convert through str() when receiving floats
    so that binary floating-point artefacts do not enter the
    engineering calculations.
    """

    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _non_negative(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert to Decimal and clamp negative values to zero.
    """

    number = _decimal(value, default)

    if number < ZERO:
        return ZERO

    return number


def _round(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Engineering rounding helper.
    """

    number = _decimal(value)

    quantum = Decimal("1").scaleb(-places)

    return number.quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )


def _number(
    value: Any,
    places: int = 2,
):
    """
    Convert Decimal to a JSON/template-friendly numeric value.

    Integers are returned as int.
    Decimal values are returned as float.
    """

    rounded = _round(value, places)

    if rounded == rounded.to_integral_value():
        return int(rounded)

    return float(rounded)


# ================================================================
# ENGINE VERSION
# ================================================================

ENGINE_NAME = "System Voltage Engine"

ENGINE_VERSION = "2.0.0"


# ================================================================
# SYSTEM VOLTAGE CLASSES
# ================================================================

"""
These are NOMINAL SYSTEM VOLTAGE CLASSES.

They are intentionally independent of individual battery voltage.

The list is deliberately extended beyond 12/24/48 V so the
calculator can support larger battery energy-storage systems.

Examples:

    12.8 V battery -> 12 V system class

    2 × 12.8 V -> 25.6 V battery bank -> 24 V system class

    4 × 12.8 V -> 51.2 V battery bank -> 48 V system class

    8 × 12.8 V -> 102.4 V battery bank -> 96 V system class

Higher-voltage systems can therefore be handled without changing
the engine.
"""

SYSTEM_VOLTAGE_CLASSES = (
    Decimal("12"),
    Decimal("24"),
    Decimal("48"),
    Decimal("96"),
    Decimal("120"),
    Decimal("192"),
    Decimal("240"),
    Decimal("384"),
)


# ================================================================
# ENGINEERING LIMITS
# ================================================================

"""
These limits represent DESIGN TARGETS for selecting a sensible
DC voltage.

They are NOT replacements for manufacturer specifications.

The actual battery, inverter, cable and protection engines must
still verify equipment-specific current capabilities later.
"""

# Maximum preferred continuous DC current.
MAX_PREFERRED_CONTINUOUS_CURRENT = Decimal("150")

# Maximum preferred surge DC current.
MAX_PREFERRED_SURGE_CURRENT = Decimal("300")

# Maximum continuous current before the engine strongly prefers
# moving to the next system voltage.
MAX_CONTINUOUS_CURRENT = Decimal("200")

# Maximum surge current before the engine strongly prefers
# moving to the next system voltage.
MAX_SURGE_CURRENT = Decimal("400")

# Minimum inverter efficiency used for current estimation when
# no valid efficiency is supplied.
DEFAULT_INVERTER_EFFICIENCY = Decimal("0.95")


# ================================================================
# LOAD-BASED FALLBACK THRESHOLDS
# ================================================================

"""
These are not the primary selection mechanism.

They provide engineering context and prevent a low voltage from
being selected for a large system even when current calculations
happen to appear acceptable.

The values represent approximate continuous power regions.
"""

POWER_GUIDANCE = (
    (Decimal("1000"), Decimal("12")),
    (Decimal("3000"), Decimal("24")),
    (Decimal("8000"), Decimal("48")),
    (Decimal("16000"), Decimal("96")),
    (Decimal("25000"), Decimal("120")),
    (Decimal("50000"), Decimal("192")),
    (Decimal("100000"), Decimal("240")),
)


# ================================================================
# VOLTAGE NORMALIZATION
# ================================================================

def normalize_system_voltage(
    voltage: Any,
) -> Optional[int]:
    """
    Normalize a system voltage into one of the supported nominal
    system classes.

    Example:

        12       -> 12
        24       -> 24
        48       -> 48
        96       -> 96

    Returns None when the voltage is not supported.
    """

    value = _decimal(voltage)

    for candidate in SYSTEM_VOLTAGE_CLASSES:
        if value == candidate:
            return int(candidate)

    return None


# ================================================================
# NEXT VOLTAGE
# ================================================================

def next_system_voltage(
    voltage: Any,
) -> Optional[int]:
    """
    Return the next supported nominal system voltage.

    Example:

        12 -> 24
        24 -> 48
        48 -> 96
        96 -> 120
        120 -> 192
        192 -> 240
        240 -> 384
        384 -> None
    """

    value = _decimal(voltage)

    for index, candidate in enumerate(
        SYSTEM_VOLTAGE_CLASSES
    ):
        if value <= candidate:
            if index + 1 >= len(SYSTEM_VOLTAGE_CLASSES):
                return None

            return int(
                SYSTEM_VOLTAGE_CLASSES[index + 1]
            )

    return None


# ================================================================
# POWER GUIDANCE VOLTAGE
# ================================================================

def voltage_from_power_guidance(
    running_load: Decimal,
) -> int:
    """
    Determine the minimum sensible voltage class from the
    continuous running load.

    This is a guidance floor, not the final selection.
    """

    for maximum_power, voltage in POWER_GUIDANCE:
        if running_load <= maximum_power:
            return int(voltage)

    return int(
        SYSTEM_VOLTAGE_CLASSES[-1]
    )


# ================================================================
# INPUT EXTRACTION
# ================================================================
def _extract_load_values(
    load_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract canonical load values from the Phase 1 Load Engine result.
    """

    calculations = load_result.get("calculations", {})
    selected = load_result.get("selected", {})
    load_rows = load_result.get("load_rows", [])

    # ------------------------------------------------------------
    # RUNNING LOAD
    # ------------------------------------------------------------

    running_load = (
        calculations.get("running_peak_load_w")
        or selected.get("connected_load_w")
        or Decimal("0")
    )

    # ------------------------------------------------------------
    # SURGE LOAD
    # ------------------------------------------------------------

    surge_load = (
        calculations.get("surge_peak_load_w")
        or calculations.get("peak_design_load_w")
        or selected.get("surge_load_w")
        or Decimal("0")
    )

    # ------------------------------------------------------------
    # MOTOR LOAD / MOTOR COUNT
    # ------------------------------------------------------------

    motor_load = Decimal("0")
    total_motors = 0
    simultaneous_start_load = Decimal("0")

    for row in load_rows:

        load_type = str(
            row.get("load_type", "")
        ).lower()

        starting_type = str(
            row.get("starting_type", "")
        ).lower()

        wattage = Decimal(
            str(
                row.get(
                    "wattage_w",
                    "0",
                )
            )
        )

        quantity = int(
            row.get(
                "quantity",
                0,
            )
        )

        row_power = (
            wattage *
            Decimal(quantity)
        )

        # Motor / inductive classification
        if load_type in {
            "motor",
            "inductive",
        }:
            motor_load += row_power
            total_motors += quantity

        # Simultaneous starting load
        if starting_type in {
            "simultaneous",
            "motor",
        }:
            simultaneous_start_load += (
                row.get(
                    "surge_power_w",
                    row_power,
                )
                if row.get("surge_power_w") is not None
                else row_power
            )

    # ------------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------------

    if simultaneous_start_load <= Decimal("0"):
        simultaneous_start_load = surge_load

    return {
        "running_load": Decimal(
            str(running_load)
        ),

        "surge_load": Decimal(
            str(surge_load)
        ),

        "motor_load": motor_load,

        "total_motors": total_motors,

        "simultaneous_start_load": Decimal(
            str(simultaneous_start_load)
        ),
    }
# ================================================================
# INVERTER EFFICIENCY
# ================================================================

def normalize_inverter_efficiency(
    inverter_efficiency: Any = None,
) -> Decimal:
    """
    Normalize inverter efficiency.

    Accepted forms:

        0.95
        95

    Both become:

        0.95
    """

    efficiency = _decimal(
        inverter_efficiency,
        DEFAULT_INVERTER_EFFICIENCY,
    )

    if efficiency <= ZERO:
        return DEFAULT_INVERTER_EFFICIENCY

    if efficiency > ONE:
        efficiency = efficiency / Decimal("100")

    if efficiency > ONE:
        efficiency = ONE

    return efficiency


# ================================================================
# CURRENT ESTIMATION
# ================================================================

def estimate_dc_current(
    power_watts: Decimal,
    system_voltage: Decimal,
    inverter_efficiency: Decimal,
) -> Decimal:
    """
    Estimate DC battery current required for a given AC power.

        I = P / (V × efficiency)
    """

    if system_voltage <= ZERO:
        return ZERO

    if inverter_efficiency <= ZERO:
        inverter_efficiency = (
            DEFAULT_INVERTER_EFFICIENCY
        )

    return (
        power_watts
        /
        (
            system_voltage
            * inverter_efficiency
        )
    )


# ================================================================
# MOTOR ANALYSIS
# ================================================================

def _motor_voltage_floor(
    running_load: Decimal,
    motor_load: Decimal,
    total_motors: int,
    simultaneous_start_load: Decimal,
) -> Dict[str, Any]:
    """
    Determine whether motor-related demand should raise the
    minimum system voltage.

    The engine uses the characteristics of the load rather than
    simply looking at total watts.
    """

    warnings: List[str] = []
    messages: List[str] = []

    if running_load > ZERO:
        motor_ratio = (
            motor_load / running_load
        )
    else:
        motor_ratio = ZERO

    if running_load > ZERO:
        surge_ratio = (
            simultaneous_start_load
            /
            running_load
        )
    else:
        surge_ratio = ZERO

    voltage_floor = Decimal("12")

    # Significant motor proportion.
    if motor_ratio >= Decimal("0.50"):
        voltage_floor = max(
            voltage_floor,
            Decimal("24"),
        )

        messages.append(
            "Motor/compressor loads represent "
            "a significant portion of the running load."
        )

    # High motor proportion.
    if motor_ratio >= Decimal("0.70"):
        voltage_floor = max(
            voltage_floor,
            Decimal("48"),
        )

        warnings.append(
            "High motor/compressor content increases "
            "DC surge-current requirements."
        )

    # Multiple motors.
    if total_motors >= 3:
        voltage_floor = max(
            voltage_floor,
            Decimal("48"),
        )

        messages.append(
            "Multiple motor loads are present; "
            "a higher DC system voltage is preferred."
        )

    # Simultaneous starting.
    if simultaneous_start_load > ZERO:

        if simultaneous_start_load >= Decimal("5000"):
            voltage_floor = max(
                voltage_floor,
                Decimal("48"),
            )

        if simultaneous_start_load >= Decimal("10000"):
            voltage_floor = max(
                voltage_floor,
                Decimal("96"),
            )

        if simultaneous_start_load >= Decimal("20000"):
            voltage_floor = max(
                voltage_floor,
                Decimal("120"),
            )

    # Very high simultaneous-start ratio.
    if surge_ratio >= Decimal("3"):
        voltage_floor = max(
            voltage_floor,
            Decimal("48"),
        )

        warnings.append(
            "The calculated starting demand is "
            "significantly higher than the running load."
        )

    if surge_ratio >= Decimal("5"):
        voltage_floor = max(
            voltage_floor,
            Decimal("96"),
        )

        warnings.append(
            "Very high surge demand detected. "
            "Verify inverter surge capability and "
            "motor starting method."
        )

    return {
        "voltage_floor": int(
            voltage_floor
        ),
        "motor_ratio": motor_ratio,
        "surge_ratio": surge_ratio,
        "warnings": warnings,
        "messages": messages,
    }


# ================================================================
# CURRENT-BASED VOLTAGE SELECTION
# ================================================================

def _select_by_current(
    minimum_voltage: Decimal,
    running_load: Decimal,
    surge_load: Decimal,
    inverter_efficiency: Decimal,
) -> Dict[str, Any]:
    """
    Starting from the minimum required voltage, move upward until
    the estimated continuous and surge currents fall within
    preferred engineering limits.

    This makes voltage selection fundamentally current-based.
    """

    candidates = []

    start_index = 0

    for index, voltage in enumerate(
        SYSTEM_VOLTAGE_CLASSES
    ):
        if voltage >= minimum_voltage:
            start_index = index
            break
    else:
        start_index = (
            len(SYSTEM_VOLTAGE_CLASSES) - 1
        )

    selected_voltage = (
        SYSTEM_VOLTAGE_CLASSES[start_index]
    )

    for voltage in SYSTEM_VOLTAGE_CLASSES[
        start_index:
    ]:

        continuous_current = (
            estimate_dc_current(
                running_load,
                voltage,
                inverter_efficiency,
            )
        )

        surge_current = (
            estimate_dc_current(
                surge_load,
                voltage,
                inverter_efficiency,
            )
        )

        simultaneous_current = (
            estimate_dc_current(
                max(
                    surge_load,
                    Decimal("0"),
                ),
                voltage,
                inverter_efficiency,
            )
        )

        preferred_ok = (
            continuous_current
            <= MAX_PREFERRED_CONTINUOUS_CURRENT
            and
            surge_current
            <= MAX_PREFERRED_SURGE_CURRENT
        )

        hard_ok = (
            continuous_current
            <= MAX_CONTINUOUS_CURRENT
            and
            surge_current
            <= MAX_SURGE_CURRENT
        )

        candidate = {
            "system_voltage": int(voltage),
            "continuous_current": continuous_current,
            "surge_current": surge_current,
            "simultaneous_current": (
                simultaneous_current
            ),
            "preferred_ok": preferred_ok,
            "hard_ok": hard_ok,
        }

        candidates.append(candidate)

        if preferred_ok:
            selected_voltage = voltage
            break

        if hard_ok:
            selected_voltage = voltage
            break

        selected_voltage = voltage

    return {
        "selected_voltage": int(
            selected_voltage
        ),
        "candidates": candidates,
    }


# ================================================================
# BATTERY-BANK INFORMATION
# ================================================================

def calculate_battery_series_requirement(
    system_voltage: Any,
    battery_nominal_voltage: Any,
) -> Dict[str, Any]:
    """
    Calculate how many batteries must be connected in series
    to achieve a nominal system class.

    This function does NOT select batteries.

    It only establishes the electrical relationship.

    Example:

        system = 48 V
        battery = 12.8 V

        series = ceil(48 / 12.8)
               = 4

        actual bank voltage
        = 4 × 12.8
        = 51.2 V

    The battery engine will later decide whether that actual
    voltage is electrically compatible with the selected
    inverter/system.
    """

    system = _decimal(system_voltage)
    battery = _decimal(
        battery_nominal_voltage
    )

    if system <= ZERO:
        return {
            "success": False,
            "series_count": 0,
            "actual_bank_voltage": ZERO,
            "voltage_error": ZERO,
            "message": (
                "System voltage must be greater than zero."
            ),
        }

    if battery <= ZERO:
        return {
            "success": False,
            "series_count": 0,
            "actual_bank_voltage": ZERO,
            "voltage_error": ZERO,
            "message": (
                "Battery nominal voltage must be "
                "greater than zero."
            ),
        }

    # Ceiling division without converting to float.
    series_count = int(
        (
            system
            / battery
        ).to_integral_value(
            rounding="ROUND_CEILING"
        )
    )

    if series_count < 1:
        series_count = 1

    actual_bank_voltage = (
        battery
        * Decimal(series_count)
    )

    voltage_error = (
        actual_bank_voltage
        - system
    )

    return {
        "success": True,
        "series_count": series_count,
        "actual_bank_voltage": (
            actual_bank_voltage
        ),
        "voltage_error": voltage_error,
        "voltage_error_percent": (
            (
                voltage_error
                /
                system
            )
            * Decimal("100")
        ),
        "message": (
            f"{series_count} battery/batteries "
            f"in series produce approximately "
            f"{actual_bank_voltage} V nominal."
        ),
    }


# ================================================================
# MAIN ENGINE
# ================================================================

def determine_system_voltage(
    load_result: Dict[str, Any],
    inverter_efficiency: Any = None,
) -> Dict[str, Any]:
    """
    Determine the recommended nominal DC system voltage.

    Parameters
    ----------
    load_result:
        Result produced by the Phase 1 load engine.

    inverter_efficiency:
        Optional inverter efficiency.

        Accepted examples:
            0.95
            95

        Defaults to 0.95.

    Returns
    -------
    dict
        Complete engineering result.
    """

    # ------------------------------------------------------------
    # BASIC INPUT VALIDATION
    # ------------------------------------------------------------

    if not isinstance(
        load_result,
        dict,
    ):
        return {
            "success": False,
            "system_voltage": None,
            "recommended_system_voltage": None,
            "minimum_system_voltage": None,
            "required": {},
            "analysis": {},
            "warnings": [
                "Load-engine result must be a dictionary."
            ],
            "messages": [],
            "candidates": [],
            "message": (
                "Load analysis is required "
                "before selecting system voltage."
            ),
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
        }

    # ------------------------------------------------------------
    # EXTRACT LOAD DATA
    # ------------------------------------------------------------

    values = _extract_load_values(
        load_result
    )

    running_load = values[
        "running_load"
    ]

    surge_load = values[
        "surge_load"
    ]

    motor_load = values[
        "motor_load"
    ]

    total_motors = values[
        "total_motors"
    ]

    simultaneous_start_load = values[
        "simultaneous_start_load"
    ]

    # ------------------------------------------------------------
    # VALIDATE NON-ZERO LOAD
    # ------------------------------------------------------------

    if running_load <= ZERO:
        return {
            "success": False,
            "system_voltage": None,
            "recommended_system_voltage": None,
            "minimum_system_voltage": None,
            "required": {
                "running_load_watts": 0,
                "surge_load_watts": (
                    _number(
                        surge_load
                    )
                ),
            },
            "analysis": {},
            "warnings": [
                "Running load must be greater than zero."
            ],
            "messages": [],
            "candidates": [],
            "message": (
                "A valid running load is required "
                "to determine system voltage."
            ),
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
        }

    # ------------------------------------------------------------
    # INVERTER EFFICIENCY
    # ------------------------------------------------------------

    efficiency = (
        normalize_inverter_efficiency(
            inverter_efficiency
        )
    )

    # ------------------------------------------------------------
    # POWER GUIDANCE
    # ------------------------------------------------------------

    power_floor = Decimal(
        voltage_from_power_guidance(
            running_load
        )
    )

    # ------------------------------------------------------------
    # MOTOR / SURGE ANALYSIS
    # ------------------------------------------------------------

    motor_analysis = (
        _motor_voltage_floor(
            running_load=running_load,
            motor_load=motor_load,
            total_motors=total_motors,
            simultaneous_start_load=(
                simultaneous_start_load
            ),
        )
    )

    motor_floor = Decimal(
        motor_analysis[
            "voltage_floor"
        ]
    )

    # ------------------------------------------------------------
    # MINIMUM SYSTEM VOLTAGE
    # ------------------------------------------------------------

    minimum_voltage = max(
        power_floor,
        motor_floor,
        Decimal("12"),
    )

    # ------------------------------------------------------------
    # CURRENT-BASED SELECTION
    # ------------------------------------------------------------

    selection = _select_by_current(
        minimum_voltage=minimum_voltage,
        running_load=running_load,
        surge_load=surge_load,
        inverter_efficiency=efficiency,
    )

    selected_voltage = Decimal(
        selection[
            "selected_voltage"
        ]
    )

    # ------------------------------------------------------------
    # CURRENT CALCULATIONS
    # ------------------------------------------------------------

    continuous_current = (
        estimate_dc_current(
            running_load,
            selected_voltage,
            efficiency,
        )
    )

    surge_current = (
        estimate_dc_current(
            surge_load,
            selected_voltage,
            efficiency,
        )
    )

    simultaneous_current = (
        estimate_dc_current(
            max(
                simultaneous_start_load,
                surge_load,
            ),
            selected_voltage,
            efficiency,
        )
    )

    # ------------------------------------------------------------
    # WARNINGS
    # ------------------------------------------------------------

    warnings: List[str] = []

    messages: List[str] = []

    warnings.extend(
        motor_analysis[
            "warnings"
        ]
    )

    messages.extend(
        motor_analysis[
            "messages"
        ]
    )

    # ------------------------------------------------------------
    # HIGH CURRENT WARNINGS
    # ------------------------------------------------------------

    if continuous_current > MAX_PREFERRED_CONTINUOUS_CURRENT:
        warnings.append(
            "Estimated continuous DC current is high. "
            "A higher system voltage may improve conductor "
            "and battery-current requirements."
        )

    if continuous_current > MAX_CONTINUOUS_CURRENT:
        warnings.append(
            "Estimated continuous DC current exceeds "
            "the preferred engineering limit. "
            "Verify battery, inverter, busbar and cable ratings."
        )

    if surge_current > MAX_PREFERRED_SURGE_CURRENT:
        warnings.append(
            "Estimated DC surge current is high. "
            "Verify inverter surge capability and battery "
            "maximum discharge current."
        )

    if surge_current > MAX_SURGE_CURRENT:
        warnings.append(
            "Estimated DC surge current is very high. "
            "A higher DC system voltage or alternative "
            "inverter architecture should be considered."
        )

    # ------------------------------------------------------------
    # VERY LARGE SYSTEM WARNING
    # ------------------------------------------------------------

    if selected_voltage >= Decimal("192"):
        warnings.append(
            "High-voltage battery architecture selected. "
            "Battery insulation, isolation, protection, "
            "clearance, creepage and equipment voltage ratings "
            "must be verified by the downstream equipment engines."
        )

    # ------------------------------------------------------------
    # SYSTEM VOLTAGE MESSAGE
    # ------------------------------------------------------------

    messages.append(
        f"{int(selected_voltage)} V nominal DC system voltage "
        f"selected from the load characteristics."
    )

    # ------------------------------------------------------------
    # ENGINEERING ANALYSIS
    # ------------------------------------------------------------

    motor_ratio = motor_analysis[
        "motor_ratio"
    ]

    surge_ratio = motor_analysis[
        "surge_ratio"
    ]

    analysis = {
        "running_load_watts": _number(
            running_load
        ),
        "surge_load_watts": _number(
            surge_load
        ),
        "motor_load_watts": _number(
            motor_load
        ),
        "total_motors": total_motors,
        "simultaneous_start_load_watts": _number(
            simultaneous_start_load
        ),
        "motor_load_ratio": _number(
            motor_ratio * Decimal("100")
        ),
        "surge_ratio": _number(
            surge_ratio
        ),
        "inverter_efficiency": _number(
            efficiency,
            places=4,
        ),
        "power_guidance_voltage": _number(
            power_floor
        ),
        "motor_voltage_floor": _number(
            motor_floor
        ),
        "minimum_system_voltage": _number(
            minimum_voltage
        ),
        "selected_system_voltage": _number(
            selected_voltage
        ),
        "estimated_continuous_dc_current": _number(
            continuous_current
        ),
        "estimated_surge_dc_current": _number(
            surge_current
        ),
        "estimated_simultaneous_start_dc_current": (
            _number(
                simultaneous_current
            )
        ),
    }

    # ------------------------------------------------------------
    # REQUIRED DATA
    # ------------------------------------------------------------

    required = {
        "system_voltage": int(
            selected_voltage
        ),
        "nominal_system_voltage": int(
            selected_voltage
        ),
        "minimum_system_voltage": int(
            minimum_voltage
        ),
        "running_load_watts": _number(
            running_load
        ),
        "surge_load_watts": _number(
            surge_load
        ),
        "estimated_battery_current": _number(
            continuous_current
        ),
        "estimated_surge_current": _number(
            surge_current
        ),
        "estimated_simultaneous_start_current": (
            _number(
                simultaneous_current
            )
        ),
    }

    # ------------------------------------------------------------
    # CANDIDATE VOLTAGES
    # ------------------------------------------------------------

    candidates = []

    for candidate in selection[
        "candidates"
    ]:

        candidates.append(
            {
                "system_voltage": candidate[
                    "system_voltage"
                ],
                "continuous_current": _number(
                    candidate[
                        "continuous_current"
                    ]
                ),
                "surge_current": _number(
                    candidate[
                        "surge_current"
                    ]
                ),
                "preferred_ok": bool(
                    candidate[
                        "preferred_ok"
                    ]
                ),
                "hard_ok": bool(
                    candidate[
                        "hard_ok"
                    ]
                ),
            }
        )

    # ------------------------------------------------------------
    # FINAL RESULT
    # ------------------------------------------------------------

    return {
        "success": True,

        # Canonical value.
        "system_voltage": int(
            selected_voltage
        ),

        # Explicit alias for clarity.
        "selected_voltage": int(
            selected_voltage
        ),

        "recommended_system_voltage": int(
            selected_voltage
        ),

        "minimum_system_voltage": int(
            minimum_voltage
        ),

        "required": required,

        "analysis": analysis,

        "warnings": warnings,

        "messages": messages,

        "candidates": candidates,

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        "message": (
            f"{int(selected_voltage)} V nominal DC "
            "system voltage selected."
        ),
    }


# ================================================================
# PUBLIC ALIASES
# ================================================================

select_system_voltage = determine_system_voltage