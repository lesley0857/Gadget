# solar/services/cable_engine.py

"""
Professional Solar PV Cable Engineering Engine.

Responsibilities
----------------
1. Calculate engineering cable requirements.
2. Calculate conductor cross-sectional area from voltage-drop limits.
3. Apply continuous-load and installation derating factors.
4. Validate ampacity and voltage rating.
5. Calculate DC, single-phase AC and three-phase AC cable requirements.
6. Orchestrate the four main solar cable circuits:
       - PV
       - Battery
       - AC
       - Protective Earth
7. Delegate database product selection to cable_selection_engine.py.

Important
---------
This module performs engineering calculations.

Database product selection is delegated to:
    cable_selection_engine.py

All engineering quantities are normalized to Decimal.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from math import sqrt
from typing import Any, Dict, Optional


# ================================================================
# EXPLICIT DEPENDENCY
# ================================================================

from .cable_selection_engine import select_cable


# ================================================================
# ENGINEERING CONSTANTS
# ================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")

# Copper resistivity at approximately 20°C.
# Unit:
#     ohm * mm² / m
#
# 0.0175 is a conventional engineering value for copper.
COPPER_RESISTIVITY = Decimal("0.0175")

# Aluminium resistivity.
ALUMINIUM_RESISTIVITY = Decimal("0.0282")

# Continuous-load design factor.
CONTINUOUS_LOAD_FACTOR = Decimal("1.25")

# Default voltage-drop design limits.
DEFAULT_PV_VOLTAGE_DROP = Decimal("3.0")
DEFAULT_BATTERY_VOLTAGE_DROP = Decimal("2.0")
DEFAULT_AC_VOLTAGE_DROP = Decimal("3.0")
DEFAULT_EARTH_VOLTAGE_DROP = Decimal("5.0")

# Default power factor for AC cable calculations.
DEFAULT_POWER_FACTOR = Decimal("0.95")

# Default distances.
#
# These are only fallback values when the calling layer does not
# supply actual cable routes.
#
# The result will contain a warning when a fallback is used.
DEFAULT_PV_DISTANCE = Decimal("10")
DEFAULT_BATTERY_DISTANCE = Decimal("2")
DEFAULT_AC_DISTANCE = Decimal("10")
DEFAULT_EARTH_DISTANCE = Decimal("10")

# Default installation derating.
DEFAULT_DERATING_FACTOR = Decimal("1.0")

# Market-standard conductor sizes.
STANDARD_CABLE_SIZES = (
    Decimal("1.5"),
    Decimal("2.5"),
    Decimal("4"),
    Decimal("6"),
    Decimal("10"),
    Decimal("16"),
    Decimal("25"),
    Decimal("35"),
    Decimal("50"),
    Decimal("70"),
    Decimal("95"),
    Decimal("120"),
    Decimal("150"),
    Decimal("185"),
    Decimal("240"),
    Decimal("300"),
)


# ================================================================
# BASIC TYPE NORMALIZATION
# ================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert numeric input to Decimal safely.

    This function is intentionally used at engine boundaries so
    Decimal values from Django models, integers from calculations,
    and string inputs do not get mixed with float arithmetic.
    """

    if isinstance(value, Decimal):
        return value

    if value is None:
        return default

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def positive_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a non-negative Decimal.
    """

    value = to_decimal(value, default)

    if value < ZERO:
        return ZERO

    return value


# ================================================================
# STANDARD SIZE SELECTION
# ================================================================

def nearest_standard_size(
    required_size: Any,
) -> Decimal:
    """
    Return the smallest standard market cable size that is
    greater than or equal to the calculated requirement.

    If the requirement exceeds the largest standard size, the
    largest standard size is returned and the caller is expected
    to issue an engineering warning.
    """

    required_size = positive_decimal(required_size)

    for size in STANDARD_CABLE_SIZES:
        if size >= required_size:
            return size

    return STANDARD_CABLE_SIZES[-1]


# ================================================================
# RESISTIVITY
# ================================================================

def get_conductor_resistivity(
    conductor_material: str = "copper",
) -> Decimal:
    """
    Return conductor resistivity.

    Supported:
        copper
        aluminium
        aluminum
    """

    material = str(
        conductor_material or "copper"
    ).strip().lower()

    if material in {
        "aluminium",
        "aluminum",
        "al",
    }:
        return ALUMINIUM_RESISTIVITY

    return COPPER_RESISTIVITY


# ================================================================
# VOLTAGE DROP PATH FACTOR
# ================================================================

def get_voltage_drop_path_factor(
    circuit_type: str,
    phase: str = "single_phase",
) -> Decimal:
    """
    Return the electrical path multiplier.

    DC:
        2 × L × I × rho / A

    Single-phase AC:
        2 × L × I × rho / A

    Three-phase AC:
        sqrt(3) × L × I × rho / A

    The function returns the multiplier used against:
        rho × I × L / A
    """

    circuit_type = str(
        circuit_type or "dc"
    ).strip().lower()

    phase = str(
        phase or "single_phase"
    ).strip().lower()

    if circuit_type == "ac" and phase == "three_phase":
        return Decimal(str(sqrt(3)))

    return Decimal("2")


# ================================================================
# ENGINEERING CABLE REQUIREMENT
# ================================================================

def calculate_cable_requirement(
    current: Any,
    voltage: Any,
    distance: Any,
    cable_type: str,
    max_voltage_drop: Any = Decimal("3"),
    *,
    circuit_type: str = "dc",
    phase: str = "single_phase",
    conductor_material: str = "copper",
    continuous_load_factor: Any = CONTINUOUS_LOAD_FACTOR,
    derating_factor: Any = DEFAULT_DERATING_FACTOR,
    minimum_ampacity_margin: Any = ONE,
    required_voltage_rating: Any = None,
    installation_method: str = "not_specified",
    design_power_factor: Any = DEFAULT_POWER_FACTOR,
) -> Dict[str, Any]:
    """
    Calculate the engineering requirement for one cable circuit.

    Parameters
    ----------
    current:
        Operating current in amperes.

    voltage:
        Circuit voltage in volts.

    distance:
        One-way physical route length in metres.

    cable_type:
        Database cable type:
            pv
            battery
            ac
            earth

    max_voltage_drop:
        Maximum allowable voltage drop in percent.

    circuit_type:
        dc or ac.

    phase:
        single_phase or three_phase.

    conductor_material:
        copper or aluminium.

    continuous_load_factor:
        Multiplier applied to operating current for design ampacity.

    derating_factor:
        Combined installation/environment derating factor.

        Example:
            1.0 = no derating
            0.8 = 20% derating

    minimum_ampacity_margin:
        Additional ampacity multiplier.

    required_voltage_rating:
        Minimum cable voltage rating required.

    installation_method:
        Informational engineering assumption.

    design_power_factor:
        Included in the engineering record for AC systems.
    """

    warnings = []

    # ------------------------------------------------------------
    # NORMALIZE INPUTS
    # ------------------------------------------------------------

    current = positive_decimal(current)
    voltage = positive_decimal(voltage)
    distance = positive_decimal(distance)

    max_voltage_drop = positive_decimal(
        max_voltage_drop,
        Decimal("3"),
    )

    continuous_load_factor = positive_decimal(
        continuous_load_factor,
        CONTINUOUS_LOAD_FACTOR,
    )

    derating_factor = positive_decimal(
        derating_factor,
        DEFAULT_DERATING_FACTOR,
    )

    minimum_ampacity_margin = positive_decimal(
        minimum_ampacity_margin,
        ONE,
    )

    required_voltage_rating = (
        positive_decimal(required_voltage_rating)
        if required_voltage_rating is not None
        else voltage
    )

    design_power_factor = positive_decimal(
        design_power_factor,
        DEFAULT_POWER_FACTOR,
    )

    circuit_type = str(
        circuit_type or "dc"
    ).strip().lower()

    phase = str(
        phase or "single_phase"
    ).strip().lower()

    cable_type = str(
        cable_type or ""
    ).strip().lower()

    # ------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------

    if current <= ZERO:
        return _failure(
            "Invalid cable current.",
            [
                "Cable design current must be greater than zero."
            ],
        )

    if voltage <= ZERO:
        return _failure(
            "Invalid cable voltage.",
            [
                "Cable circuit voltage must be greater than zero."
            ],
        )

    if distance <= ZERO:
        return _failure(
            "Invalid cable distance.",
            [
                "Cable route distance must be greater than zero."
            ],
        )

    if max_voltage_drop <= ZERO:
        return _failure(
            "Invalid voltage-drop limit.",
            [
                "Maximum allowable voltage drop must be greater than zero."
            ],
        )

    if derating_factor <= ZERO or derating_factor > ONE:
        return _failure(
            "Invalid cable derating factor.",
            [
                "Derating factor must be greater than zero and "
                "less than or equal to 1.0."
            ],
        )

    if continuous_load_factor <= ZERO:
        return _failure(
            "Invalid continuous-load factor.",
            [
                "Continuous-load factor must be greater than zero."
            ],
        )

    if minimum_ampacity_margin <= ZERO:
        return _failure(
            "Invalid ampacity margin.",
            [
                "Ampacity margin must be greater than zero."
            ],
        )

    if circuit_type not in {"dc", "ac"}:
        return _failure(
            "Invalid circuit type.",
            [
                "Circuit type must be either 'dc' or 'ac'."
            ],
        )

    if circuit_type == "ac" and phase not in {
        "single_phase",
        "three_phase",
    }:
        return _failure(
            "Invalid AC phase configuration.",
            [
                "AC phase must be 'single_phase' or 'three_phase'."
            ],
        )

    # ------------------------------------------------------------
    # RESISTIVITY
    # ------------------------------------------------------------

    resistivity = get_conductor_resistivity(
        conductor_material
    )

    # ------------------------------------------------------------
    # DESIGN CURRENT
    # ------------------------------------------------------------

    design_current = (
        current
        * continuous_load_factor
    )

    # ------------------------------------------------------------
    # REQUIRED AMPACITY
    #
    # Cable ampacity must withstand the design current after
    # installation derating.
    #
    # Required database ampacity:
    #
    # I_required =
    #     I_design × ampacity_margin / derating_factor
    # ------------------------------------------------------------

    required_ampacity = (
        design_current
        * minimum_ampacity_margin
        / derating_factor
    )

    # ------------------------------------------------------------
    # ALLOWABLE VOLTAGE DROP
    # ------------------------------------------------------------

    allowable_voltage_drop = (
        voltage
        * max_voltage_drop
        / HUNDRED
    )

    if allowable_voltage_drop <= ZERO:
        return _failure(
            "Invalid allowable voltage drop.",
            [
                "Calculated allowable voltage drop is zero."
            ],
        )

    # ------------------------------------------------------------
    # ELECTRICAL PATH FACTOR
    # ------------------------------------------------------------

    path_factor = get_voltage_drop_path_factor(
        circuit_type=circuit_type,
        phase=phase,
    )

    # ------------------------------------------------------------
    # REQUIRED CROSS-SECTIONAL AREA
    #
    # Vd = K × rho × I × L / A
    #
    # therefore:
    #
    # A = K × rho × I × L / Vd
    # ------------------------------------------------------------

    calculated_size = (
        path_factor
        * resistivity
        * design_current
        * distance
        / allowable_voltage_drop
    )

    required_size = nearest_standard_size(
        calculated_size
    )

    # ------------------------------------------------------------
    # TOTAL CONDUCTOR LENGTH
    #
    # DC and single-phase AC:
    #       outgoing + return
    #
    # Three-phase:
    #       electrical path is represented by the sqrt(3)
    #       formula, therefore physical route remains one-way.
    # ------------------------------------------------------------

    if circuit_type == "ac" and phase == "three_phase":
        total_conductor_length = distance
    else:
        total_conductor_length = distance * Decimal("2")

    # ------------------------------------------------------------
    # ACTUAL VOLTAGE DROP
    # ------------------------------------------------------------

    actual_voltage_drop = (
        path_factor
        * resistivity
        * design_current
        * distance
        / required_size
    )

    voltage_drop_percent = (
        actual_voltage_drop
        / voltage
        * HUNDRED
    )

    # ------------------------------------------------------------
    # WARNINGS
    # ------------------------------------------------------------

    if voltage_drop_percent > max_voltage_drop:
        warnings.append(
            "Selected standard cable does not satisfy the "
            "specified voltage-drop limit."
        )

    if calculated_size > STANDARD_CABLE_SIZES[-1]:
        warnings.append(
            "Calculated conductor size exceeds the largest "
            "standard market size in the engineering library."
        )

    if design_current > current:
        warnings.append(
            "Cable design current includes the configured "
            "continuous-load factor."
        )

    if derating_factor < ONE:
        warnings.append(
            "Cable ampacity has been adjusted for installation "
            "derating."
        )

    if installation_method == "not_specified":
        warnings.append(
            "Installation method was not explicitly specified. "
            "Ampacity verification should be confirmed against "
            "the actual installation method and applicable standard."
        )

    # ------------------------------------------------------------
    # ENGINEERING REQUIREMENT
    # ------------------------------------------------------------

    requirement = {
        "cable_type": cable_type,

        "circuit_type": circuit_type,

        "phase": phase,

        "conductor_material": conductor_material,

        "installation_method": installation_method,

        "current": current,

        "design_current": design_current,

        "required_current": design_current,

        "required_ampacity": required_ampacity,

        "system_voltage": voltage,

        "required_voltage_rating": required_voltage_rating,

        "distance": distance,

        "length": total_conductor_length,

        "allowable_voltage_drop": max_voltage_drop,

        "allowable_voltage_drop_volts":
            allowable_voltage_drop,

        "calculated_size": calculated_size,

        "required_size": required_size,

        "actual_voltage_drop":
            actual_voltage_drop,

        "voltage_drop":
            voltage_drop_percent,

        "continuous_load_factor":
            continuous_load_factor,

        "derating_factor":
            derating_factor,

        "ampacity_margin":
            minimum_ampacity_margin,

        "resistivity":
            resistivity,

        "power_factor":
            design_power_factor,
    }

    return {
        "success": True,

        "requirement": _serialize_engineering_values(
            requirement
        ),

        "design": _serialize_engineering_values(
            requirement
        ),

        "message":
            "Cable engineering requirement calculated successfully.",

        "warnings": warnings,
    }


# ================================================================
# PV CABLE
# ================================================================

def calculate_dc_cable(
    current: Any,
    voltage: Any,
    distance: Any,
    *,
    max_voltage_drop: Any = DEFAULT_PV_VOLTAGE_DROP,
    derating_factor: Any = DEFAULT_DERATING_FACTOR,
    installation_method: str = "pv_dc",
    conductor_material: str = "copper",
) -> Dict[str, Any]:
    """
    PV/DC cable engineering calculation.
    """

    return calculate_cable_requirement(
        current=current,
        voltage=voltage,
        distance=distance,
        cable_type="pv",
        max_voltage_drop=max_voltage_drop,
        circuit_type="dc",
        phase="single_phase",
        conductor_material=conductor_material,
        continuous_load_factor=CONTINUOUS_LOAD_FACTOR,
        derating_factor=derating_factor,
        installation_method=installation_method,
        required_voltage_rating=voltage,
    )


# ================================================================
# BATTERY CABLE
# ================================================================

def battery_cable(
    inverter_power: Any,
    battery_voltage: Any,
    efficiency: Any = Decimal("0.90"),
    distance: Any = DEFAULT_BATTERY_DISTANCE,
    *,
    max_voltage_drop: Any = DEFAULT_BATTERY_VOLTAGE_DROP,
    derating_factor: Any = DEFAULT_DERATING_FACTOR,
    installation_method: str = "battery_dc",
    conductor_material: str = "copper",
) -> Dict[str, Any]:
    """
    Battery-to-inverter DC cable calculation.

    DC current is derived from inverter power and battery voltage.

    I = P / (V × eta)

    A 125% continuous design factor is subsequently applied by
    calculate_cable_requirement().
    """

    inverter_power = positive_decimal(
        inverter_power
    )

    battery_voltage = positive_decimal(
        battery_voltage
    )

    efficiency = positive_decimal(
        efficiency,
        Decimal("0.90"),
    )

    if inverter_power <= ZERO:
        return _failure(
            "Invalid inverter power for battery cable.",
            [
                "Inverter power must be greater than zero."
            ],
        )

    if battery_voltage <= ZERO:
        return _failure(
            "Invalid battery voltage for battery cable.",
            [
                "Battery voltage must be greater than zero."
            ],
        )

    if efficiency <= ZERO:
        return _failure(
            "Invalid inverter efficiency for battery cable.",
            [
                "Inverter efficiency must be greater than zero."
            ],
        )

    operating_current = (
        inverter_power
        /
        (
            battery_voltage
            * efficiency
        )
    )

    return calculate_cable_requirement(
        current=operating_current,
        voltage=battery_voltage,
        distance=distance,
        cable_type="battery",
        max_voltage_drop=max_voltage_drop,
        circuit_type="dc",
        phase="single_phase",
        conductor_material=conductor_material,
        continuous_load_factor=CONTINUOUS_LOAD_FACTOR,
        derating_factor=derating_factor,
        installation_method=installation_method,
        required_voltage_rating=battery_voltage,
    )


# ================================================================
# AC CABLE
# ================================================================

def calculate_ac_cable(
    power: Any,
    voltage: Any,
    distance: Any,
    *,
    phase: str = "single_phase",
    power_factor: Any = DEFAULT_POWER_FACTOR,
    efficiency: Any = ONE,
    max_voltage_drop: Any = DEFAULT_AC_VOLTAGE_DROP,
    derating_factor: Any = DEFAULT_DERATING_FACTOR,
    installation_method: str = "ac_output",
    conductor_material: str = "copper",
) -> Dict[str, Any]:
    """
    AC output cable calculation.

    Single phase:
        I = P / (V × PF × eta)

    Three phase:
        I = P / (sqrt(3) × V × PF × eta)
    """

    power = positive_decimal(power)
    voltage = positive_decimal(voltage)

    power_factor = positive_decimal(
        power_factor,
        DEFAULT_POWER_FACTOR,
    )

    efficiency = positive_decimal(
        efficiency,
        ONE,
    )

    if power <= ZERO:
        return _failure(
            "Invalid AC power.",
            [
                "AC power must be greater than zero."
            ],
        )

    if voltage <= ZERO:
        return _failure(
            "Invalid AC voltage.",
            [
                "AC voltage must be greater than zero."
            ],
        )

    if power_factor <= ZERO:
        return _failure(
            "Invalid AC power factor.",
            [
                "Power factor must be greater than zero."
            ],
        )

    if efficiency <= ZERO:
        return _failure(
            "Invalid AC efficiency.",
            [
                "Efficiency must be greater than zero."
            ],
        )

    phase = str(
        phase or "single_phase"
    ).strip().lower()

    if phase == "three_phase":
        denominator = (
            Decimal(str(sqrt(3)))
            * voltage
            * power_factor
            * efficiency
        )
    else:
        denominator = (
            voltage
            * power_factor
            * efficiency
        )

    current = power / denominator

    return calculate_cable_requirement(
        current=current,
        voltage=voltage,
        distance=distance,
        cable_type="ac",
        max_voltage_drop=max_voltage_drop,
        circuit_type="ac",
        phase=phase,
        conductor_material=conductor_material,
        continuous_load_factor=CONTINUOUS_LOAD_FACTOR,
        derating_factor=derating_factor,
        installation_method=installation_method,
        required_voltage_rating=voltage,
        design_power_factor=power_factor,
    )


# ================================================================
# EARTH / PROTECTIVE CONDUCTOR
# ================================================================

def calculate_earth_cable(
    phase_size: Any,
    distance: Any = DEFAULT_EARTH_DISTANCE,
    *,
    installation_method: str = "protective_earth",
    conductor_material: str = "copper",
    required_voltage_rating: Any = Decimal("300"),
) -> Dict[str, Any]:
    """
    Protective conductor preliminary sizing.

    This implements the common simplified conductor-area rule:

        S_PE = S_phase
            for S_phase <= 16 mm²

        S_PE = 16 mm²
            for 16 < S_phase <= 35 mm²

        S_PE = S_phase / 2
            for S_phase > 35 mm²

    Final PE sizing must still be verified against the applicable
    installation standard, fault-current, disconnection time and
    installation conditions.

    The earth conductor is not sized using normal load current.
    """

    phase_size = positive_decimal(
        phase_size
    )

    if phase_size <= ZERO:
        return _failure(
            "Invalid phase conductor size.",
            [
                "Phase conductor size must be greater than zero."
            ],
        )

    if phase_size <= Decimal("16"):
        earth_size = phase_size
    elif phase_size <= Decimal("35"):
        earth_size = Decimal("16")
    else:
        earth_size = phase_size / Decimal("2")

    earth_size = nearest_standard_size(
        earth_size
    )

    return calculate_cable_requirement(
        current=max(
            earth_size,
            Decimal("16"),
        ),
        voltage=Decimal("230"),
        distance=distance,
        cable_type="earth",
        max_voltage_drop=DEFAULT_EARTH_VOLTAGE_DROP,
        circuit_type="ac",
        phase="single_phase",
        conductor_material=conductor_material,
        continuous_load_factor=ONE,
        derating_factor=ONE,
        installation_method=installation_method,
        required_voltage_rating=required_voltage_rating,
    )


# Backwards-compatible public name.
def earth_cable(
    phase_size: Any,
    distance: Any = DEFAULT_EARTH_DISTANCE,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Backwards-compatible wrapper around calculate_earth_cable().
    """

    return calculate_earth_cable(
        phase_size=phase_size,
        distance=distance,
        **kwargs,
    )


# ================================================================
# RESULT HELPERS
# ================================================================

def _failure(
    message: str,
    warnings: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Standard engineering failure structure.
    """

    return {
        "success": False,
        "requirement": None,
        "design": None,
        "message": message,
        "warnings": warnings or [],
    }


def _serialize_engineering_values(
    value: Any,
) -> Any:
    """
    Convert Decimal values into JSON-safe values.

    JSONField cannot store Decimal objects directly.

    Engineering precision is retained by converting Decimal to
    string rather than silently converting it to binary float.
    """

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            key: _serialize_engineering_values(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _serialize_engineering_values(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _serialize_engineering_values(item)
            for item in value
        ]

    return value


# ================================================================
# RESULT NORMALIZATION
# ================================================================

def _get_nested(
    data: Optional[Dict[str, Any]],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Safely retrieve nested dictionary values.
    """

    current = data or {}

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def _get_first(
    data: Optional[Dict[str, Any]],
    paths: list[tuple[str, ...]],
    default: Any = None,
) -> Any:
    """
    Return the first available value from several possible
    result paths.

    This allows Phase 7 to consume the canonical outputs of
    Phases 2-6 while remaining tolerant of harmless naming
    differences between result layers.
    """

    for path in paths:
        value = _get_nested(
            data,
            *path,
            default=None,
        )

        if value is not None:
            return value

    return default


# ================================================================
# INVERTER INFORMATION
# ================================================================

def _get_inverter_power(
    inverter_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract inverter rated/required power.
    """

    value = _get_first(
        inverter_result,
        [
            ("selected", "rated_power"),
            ("required", "rated_power"),
            ("required", "required_power"),
            ("required", "continuous_power"),
            ("design", "rated_power"),
        ],
        default=ZERO,
    )

    return positive_decimal(value)


def _get_inverter_efficiency(
    inverter_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract inverter efficiency.
    """

    value = _get_first(
        inverter_result,
        [
            ("selected", "efficiency"),
            ("required", "efficiency"),
            ("design", "efficiency"),
        ],
        default=Decimal("0.95"),
    )

    return positive_decimal(
        value,
        Decimal("0.95"),
    )


def _get_inverter_voltage(
    inverter_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract AC output voltage.
    """

    value = _get_first(
        inverter_result,
        [
            ("selected", "output_voltage"),
            ("required", "output_voltage"),
            ("design", "output_voltage"),
        ],
        default=Decimal("230"),
    )

    return positive_decimal(
        value,
        Decimal("230"),
    )


def _get_inverter_phase(
    inverter_result: Optional[Dict[str, Any]],
) -> str:
    """
    Extract inverter phase.
    """

    value = _get_first(
        inverter_result,
        [
            ("selected", "phase"),
            ("required", "phase"),
            ("design", "phase"),
        ],
        default="single_phase",
    )

    return str(
        value or "single_phase"
    )


# ================================================================
# BATTERY INFORMATION
# ================================================================

def _get_battery_voltage(
    battery_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract canonical battery/system voltage.
    """

    value = _get_first(
        battery_result,
        [
            ("selected", "system_voltage"),
            ("selected", "bank_voltage"),
            ("required", "system_voltage"),
            ("required", "bank_voltage"),
            ("system_voltage",),
        ],
        default=ZERO,
    )

    return positive_decimal(value)


# ================================================================
# PV INFORMATION
# ================================================================

def _get_pv_voltage(
    panel_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract PV array operating voltage.
    """

    value = _get_first(
        panel_result,
        [
            ("selected", "array_voltage"),
            ("selected", "operating_voltage"),
            ("required", "array_voltage"),
            ("design", "array_voltage"),
        ],
        default=ZERO,
    )

    return positive_decimal(value)


def _get_pv_current(
    panel_result: Optional[Dict[str, Any]],
) -> Decimal:
    """
    Extract PV array operating current.
    """

    value = _get_first(
        panel_result,
        [
            ("selected", "array_current"),
            ("selected", "operating_current"),
            ("required", "array_current"),
            ("design", "array_current"),
        ],
        default=ZERO,
    )

    return positive_decimal(value)


# ================================================================
# MAIN CABLE ORCHESTRATOR
# ================================================================

def calculate_cables(
    *,
    load_analysis: Optional[Dict[str, Any]] = None,
    battery_result: Optional[Dict[str, Any]] = None,
    panel_result: Optional[Dict[str, Any]] = None,
    inverter_result: Optional[Dict[str, Any]] = None,
    controller_result: Optional[Dict[str, Any]] = None,
    operating_mode: str = "off_grid",
    pv_distance: Any = None,
    battery_distance: Any = None,
    ac_distance: Any = None,
    earth_distance: Any = None,
    installation_method: str = "not_specified",
    derating_factor: Any = DEFAULT_DERATING_FACTOR,
    pv_voltage_drop: Any = DEFAULT_PV_VOLTAGE_DROP,
    battery_voltage_drop: Any = DEFAULT_BATTERY_VOLTAGE_DROP,
    ac_voltage_drop: Any = DEFAULT_AC_VOLTAGE_DROP,
    conductor_material: str = "copper",
    power_factor: Any = DEFAULT_POWER_FACTOR,
) -> Dict[str, Any]:
    """
    Complete Phase 7 cable-design orchestrator.

    This function consumes outputs from the previous engineering
    stages and produces:

        requirement
        battery_cable
        pv_cable
        ac_cable
        earth_cable
        warnings
        engineering_messages
        summary

    Database product selection is performed by
    cable_selection_engine.select_cable().
    """

    warnings = []
    engineering_messages = []

    # ------------------------------------------------------------
    # DISTANCE NORMALIZATION
    # ------------------------------------------------------------

    if pv_distance is None:
        pv_distance = DEFAULT_PV_DISTANCE
        warnings.append(
            "PV cable route distance was not supplied. "
            f"Fallback value of {pv_distance} m was used."
        )

    if battery_distance is None:
        battery_distance = DEFAULT_BATTERY_DISTANCE
        warnings.append(
            "Battery cable route distance was not supplied. "
            f"Fallback value of {battery_distance} m was used."
        )

    if ac_distance is None:
        ac_distance = DEFAULT_AC_DISTANCE
        warnings.append(
            "AC cable route distance was not supplied. "
            f"Fallback value of {ac_distance} m was used."
        )

    if earth_distance is None:
        earth_distance = ac_distance
        warnings.append(
            "Earth cable route distance was not supplied. "
            "AC cable route distance was used as the fallback."
        )

    pv_distance = positive_decimal(pv_distance)
    battery_distance = positive_decimal(battery_distance)
    ac_distance = positive_decimal(ac_distance)
    earth_distance = positive_decimal(earth_distance)

    # ------------------------------------------------------------
    # BATTERY
    # ------------------------------------------------------------

    battery_voltage = _get_battery_voltage(
        battery_result
    )

    inverter_power = _get_inverter_power(
        inverter_result
    )

    inverter_efficiency = _get_inverter_efficiency(
        inverter_result
    )

    # ------------------------------------------------------------
    # PV
    # ------------------------------------------------------------

    pv_voltage = _get_pv_voltage(
        panel_result
    )

    pv_current = _get_pv_current(
        panel_result
    )

    # ------------------------------------------------------------
    # INVERTER AC
    # ------------------------------------------------------------

    ac_voltage = _get_inverter_voltage(
        inverter_result
    )

    ac_phase = _get_inverter_phase(
        inverter_result
    )

    # ------------------------------------------------------------
    # INPUT VALIDATION
    # ------------------------------------------------------------

    if battery_voltage <= ZERO:
        engineering_messages.append(
            "Battery cable could not be calculated because "
            "the battery/system voltage was not available."
        )

    if inverter_power <= ZERO:
        engineering_messages.append(
            "Battery and AC cable calculations could not be "
            "completed because inverter power was not available."
        )

    if pv_voltage <= ZERO:
        engineering_messages.append(
            "PV cable could not be calculated because the "
            "PV array voltage was not available."
        )

    if pv_current <= ZERO:
        engineering_messages.append(
            "PV cable could not be calculated because the "
            "PV array current was not available."
        )

    # ------------------------------------------------------------
    # BATTERY CABLE
    # ------------------------------------------------------------

    if battery_voltage > ZERO and inverter_power > ZERO:

        battery_result_engine = battery_cable(
            inverter_power=inverter_power,
            battery_voltage=battery_voltage,
            efficiency=inverter_efficiency,
            distance=battery_distance,
            max_voltage_drop=battery_voltage_drop,
            derating_factor=derating_factor,
            installation_method=installation_method,
            conductor_material=conductor_material,
        )

    else:

        battery_result_engine = _failure(
            "Battery cable requirement unavailable.",
            [
                "Battery voltage and inverter power are required."
            ],
        )

    # ------------------------------------------------------------
    # PV CABLE
    # ------------------------------------------------------------

    if pv_voltage > ZERO and pv_current > ZERO:

        pv_result_engine = calculate_dc_cable(
            current=pv_current,
            voltage=pv_voltage,
            distance=pv_distance,
            max_voltage_drop=pv_voltage_drop,
            derating_factor=derating_factor,
            installation_method=installation_method,
            conductor_material=conductor_material,
        )

    else:

        pv_result_engine = _failure(
            "PV cable requirement unavailable.",
            [
                "PV array voltage and current are required."
            ],
        )

    # ------------------------------------------------------------
    # AC CABLE
    # ------------------------------------------------------------

    if inverter_power > ZERO and ac_voltage > ZERO:

        ac_result_engine = calculate_ac_cable(
            power=inverter_power,
            voltage=ac_voltage,
            distance=ac_distance,
            phase=ac_phase,
            power_factor=power_factor,
            efficiency=ONE,
            max_voltage_drop=ac_voltage_drop,
            derating_factor=derating_factor,
            installation_method=installation_method,
            conductor_material=conductor_material,
        )

    else:

        ac_result_engine = _failure(
            "AC cable requirement unavailable.",
            [
                "Inverter power and AC output voltage are required."
            ],
        )

    # ------------------------------------------------------------
    # EARTH CABLE
    # ------------------------------------------------------------

    phase_size = _get_first(
        ac_result_engine,
        [
            ("requirement", "required_size"),
        ],
        default=ZERO,
    )

    if positive_decimal(phase_size) > ZERO:

        earth_result_engine = calculate_earth_cable(
            phase_size=phase_size,
            distance=earth_distance,
            installation_method=installation_method,
            conductor_material=conductor_material,
            required_voltage_rating=ac_voltage,
        )

    else:

        earth_result_engine = _failure(
            "Protective earth cable requirement unavailable.",
            [
                "AC phase conductor size is required to determine "
                "the preliminary protective conductor size."
            ],
        )

    # ------------------------------------------------------------
    # ENGINEERING RESULT STATUS
    # ------------------------------------------------------------

    engineering_results = {
        "battery": battery_result_engine,
        "pv": pv_result_engine,
        "ac": ac_result_engine,
        "earth": earth_result_engine,
    }

    for circuit_name, result in engineering_results.items():

        if not result.get("success", False):

            engineering_messages.append(
                f"{circuit_name.upper()} cable: "
                f"{result.get('message', 'Engineering calculation failed.')}"
            )

        warnings.extend(
            result.get(
                "warnings",
                [],
            )
        )

    # ------------------------------------------------------------
    # DATABASE SELECTION
    # ------------------------------------------------------------

    battery_selection = _select_from_requirement(
        battery_result_engine
    )

    pv_selection = _select_from_requirement(
        pv_result_engine
    )

    ac_selection = _select_from_requirement(
        ac_result_engine
    )

    earth_selection = _select_from_requirement(
        earth_result_engine
    )

    selection_results = {
        "battery": battery_selection,
        "pv": pv_selection,
        "ac": ac_selection,
        "earth": earth_selection,
    }

    for circuit_name, result in selection_results.items():

        warnings.extend(
            result.get(
                "warnings",
                [],
            )
        )

        if not result.get("success", False):

            engineering_messages.append(
                f"{circuit_name.upper()} cable selection: "
                f"{result.get('message', 'No suitable cable selected.')}"
            )

    # ------------------------------------------------------------
    # TEMPLATE-COMPATIBLE SELECTED CABLES
    # ------------------------------------------------------------

    battery_cable_result = _build_selected_cable_result(
        selection=battery_selection,
        requirement_result=battery_result_engine,
    )

    pv_cable_result = _build_selected_cable_result(
        selection=pv_selection,
        requirement_result=pv_result_engine,
    )

    ac_cable_result = _build_selected_cable_result(
        selection=ac_selection,
        requirement_result=ac_result_engine,
    )

    earth_cable_result = _build_selected_cable_result(
        selection=earth_selection,
        requirement_result=earth_result_engine,
    )

    # ------------------------------------------------------------
    # REQUIREMENT SUMMARY
    #
    # These keys are deliberately preserved for your existing
    # result template.
    # ------------------------------------------------------------

    requirement_summary = {
        "battery_current":
            _get_first(
                battery_result_engine,
                [
                    ("requirement", "required_current"),
                ],
                default=ZERO,
            ),

        "pv_current":
            _get_first(
                pv_result_engine,
                [
                    ("requirement", "required_current"),
                ],
                default=ZERO,
            ),

        "inverter_output_current":
            _get_first(
                ac_result_engine,
                [
                    ("requirement", "required_current"),
                ],
                default=ZERO,
            ),

        "earth_current":
            _get_first(
                earth_result_engine,
                [
                    ("requirement", "required_current"),
                ],
                default=ZERO,
            ),

        "allowable_voltage_drop":
            ac_voltage_drop,

        "installation_method":
            installation_method,

        "battery_voltage":
            battery_voltage,

        "pv_voltage":
            pv_voltage,

        "ac_voltage":
            ac_voltage,

        "pv_distance":
            pv_distance,

        "battery_distance":
            battery_distance,

        "ac_distance":
            ac_distance,

        "earth_distance":
            earth_distance,

        "derating_factor":
            to_decimal(
                derating_factor,
                DEFAULT_DERATING_FACTOR,
            ),

        "power_factor":
            to_decimal(
                power_factor,
                DEFAULT_POWER_FACTOR,
            ),
    }

    requirement_summary = _serialize_engineering_values(
        requirement_summary
    )

    # ------------------------------------------------------------
    # FINAL STATUS
    #
    # Engineering calculations are considered successful when
    # the engine has produced its calculations.
    #
    # Inventory absence does not crash the design.
    # Instead it appears in warnings/messages and the closest
    # product is exposed.
    # ------------------------------------------------------------

    engineering_success = all(
        result.get("success", False)
        for result in engineering_results.values()
    )

    return {
        "success": engineering_success,

        "requirement":
            requirement_summary,

        "battery_cable":
            battery_cable_result,

        "pv_cable":
            pv_cable_result,

        "ac_cable":
            ac_cable_result,

        "earth_cable":
            earth_cable_result,

        "engineering": {
            "battery":
                battery_result_engine,

            "pv":
                pv_result_engine,

            "ac":
                ac_result_engine,

            "earth":
                earth_result_engine,
        },

        "selection": {
            "battery":
                battery_selection,

            "pv":
                pv_selection,

            "ac":
                ac_selection,

            "earth":
                earth_selection,
        },

        "summary": {
            "cable_types": 4,

            "engineering_complete":
                engineering_success,

            "database_selection_complete": all(
                result.get("success", False)
                for result in selection_results.values()
            ),

            "selected_count":
                sum(
                    1
                    for result in selection_results.values()
                    if result.get("success", False)
                    and result.get("selected")
                ),
        },

        "message": (
            "Cable engineering completed successfully."
            if engineering_success
            else
            "Cable engineering completed with one or more "
            "engineering requirements unavailable."
        ),

        "warnings":
            list(dict.fromkeys(warnings)),

        "engineering_messages":
            list(dict.fromkeys(engineering_messages)),
    }


# ================================================================
# SELECTION WRAPPER
# ================================================================

def _select_from_requirement(
    engineering_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pass an engineering requirement to the database-selection
    engine only when engineering succeeded.
    """

    if not engineering_result.get("success", False):

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                engineering_result.get(
                    "message",
                    "Cable engineering requirement unavailable.",
                ),
            "warnings":
                engineering_result.get(
                    "warnings",
                    [],
                ),
        }

    requirement = engineering_result.get(
        "requirement"
    )

    if not requirement:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "Cable engineering requirement is empty.",
            "warnings": [],
        }

    return select_cable(
        cable_requirement=requirement
    )


# ================================================================
# TEMPLATE RESULT BUILDER
# ================================================================

def _build_selected_cable_result(
    selection: Dict[str, Any],
    requirement_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Convert the database selection result into the compact
    structure expected by the existing templates.
    """

    selected = selection.get(
        "selected"
    )

    if not selected:
        return None

    requirement = requirement_result.get(
        "requirement",
        {},
    )

    return {
        "cable":
            selected.get(
                "name",
                "Cable",
            ),

        "manufacturer":
            selected.get(
                "manufacturer"
            ),

        "database_id":
            selected.get(
                "id"
            ),

        "size_mm2":
            selected.get(
                "size_mm"
            ),

        "ampacity":
            selected.get(
                "ampacity"
            ),

        "current_rating":
            selected.get(
                "ampacity"
            ),

        "voltage_rating":
            selected.get(
                "voltage_rating"
            ),

        "required_current":
            requirement.get(
                "required_current"
            ),

        "length":
            requirement.get(
                "length"
            ),

        "voltage_drop":
            requirement.get(
                "actual_voltage_drop"
            ),

        "voltage_drop_percent":
            requirement.get(
                "voltage_drop"
            ),

        "unit_price":
            selected.get(
                "price_per_meter"
            ),

        "total_cost":
            selected.get(
                "total_price"
            ),

        "selection_reason":
            selected.get(
                "selection_reason"
            ),

        "cable_type":
            selected.get(
                "cable_type"
            ),

        "engineering_requirement":
            requirement,
    }