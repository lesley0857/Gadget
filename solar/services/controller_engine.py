"""
solar/services/controller_engine.py

PHASE 6
CHARGE CONTROLLER / MPPT ENGINE

This is the engineering layer for charge-controller sizing.

Responsibilities
----------------
1. Receive the canonical system voltage from Phase 2 / Phase 3.
2. Receive the selected PV array from Phase 4.
3. Determine:
       - PV operating voltage
       - PV maximum/cold Voc
       - PV operating current
       - PV short-circuit current
       - installed PV power
4. Determine the required MPPT charge-current capacity.
5. Determine the minimum controller PV-voltage rating.
6. Determine the minimum controller PV-current rating.
7. Determine the required controller power capacity.
8. Determine controller quantity where one controller is insufficient.
9. Validate controller suitability.
10. Return a complete, predictable engineering result.

Important engineering principle
--------------------------------
PV voltage and PV current are NOT interchangeable.

A controller must satisfy:

    controller PV voltage rating
        >= actual maximum PV string Voc

AND

    controller PV current rating
        >= actual PV array current requirement

AND

    controller charging-current capacity
        >= required battery charging current

AND

    controller battery voltage
        == system/battery nominal voltage

The engine never silently selects an undersized controller.

All calculations use Decimal.

No database selection occurs here.

Database selection belongs to:
    controller_selection_engine.py
"""

from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_HALF_UP,
)

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
)


# ==================================================================
# ENGINE METADATA
# ==================================================================

ENGINE_NAME = "Charge Controller / MPPT Engineering Engine"
ENGINE_VERSION = "6.0.0"


# ==================================================================
# DECIMAL CONSTANTS
# ==================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
THOUSAND = Decimal("1000")


# ==================================================================
# ENGINEERING DEFAULTS
# ==================================================================

DEFAULT_CONTROLLER_SAFETY_FACTOR = Decimal("1.25")

DEFAULT_PV_VOLTAGE_MARGIN = Decimal("1.05")

DEFAULT_PV_CURRENT_MARGIN = Decimal("1.25")

DEFAULT_CHARGE_CURRENT_MARGIN = Decimal("1.25")

DEFAULT_CONTROLLER_EFFICIENCY = Decimal("0.98")

DEFAULT_CONTROLLER_POWER_FACTOR = Decimal("1.00")

DEFAULT_BATTERY_CHARGE_VOLTAGE_FACTOR = Decimal("1.00")


# ==================================================================
# SAFE DECIMAL UTILITIES
# ==================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert input into Decimal.

    Float values are converted through str() so that binary
    floating-point artefacts do not enter engineering calculations.
    """

    if value is None:
        return default

    if isinstance(
        value,
        Decimal,
    ):
        return value

    try:
        return Decimal(
            str(value)
        )

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
    Return a positive Decimal.
    """

    number = to_decimal(
        value,
        default,
    )

    if number <= ZERO:
        return default

    return number


def non_negative(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a non-negative Decimal.
    """

    number = to_decimal(
        value,
        default,
    )

    if number < ZERO:
        return ZERO

    return number


def normalize_factor(
    value: Any,
    default: Decimal,
) -> Decimal:
    """
    Normalize a factor.

    Supports:

        1.25
        125

    where 125 is interpreted as 125%.
    """

    number = to_decimal(
        value,
        default,
    )

    if number <= ZERO:
        return default

    if number > HUNDRED:
        number /= HUNDRED

    return number


def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Round engineering values consistently.
    """

    number = to_decimal(
        value
    )

    quantum = Decimal(
        "1"
    ).scaleb(
        -places
    )

    return number.quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )


def ceil_decimal(
    value: Any,
) -> int:
    """
    Ceiling to the next whole number.
    """

    number = to_decimal(
        value
    )

    return int(
        number.to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def output_number(
    value: Any,
    places: int = 2,
):
    """
    Convert Decimal to a JSON-safe number.
    """

    number = round_decimal(
        value,
        places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ==================================================================
# ARRAY VALUE EXTRACTION
# ==================================================================

def extract_array_value(
    panel_result: Optional[Dict[str, Any]],
    keys: Iterable[str],
    default: Decimal = ZERO,
) -> Decimal:
    """
    Search multiple possible Phase 4 output locations.

    This gives Phase 6 a stable interface while still allowing
    Phase 4's detailed result structure to evolve internally.
    """

    if not isinstance(
        panel_result,
        dict,
    ):
        return default

    sources = [
        panel_result
    ]

    for key in (
        "selected",
        "engineering",
        "design",
        "required",
    ):

        value = panel_result.get(
            key
        )

        if isinstance(
            value,
            dict,
        ):
            sources.append(
                value
            )

    for source in sources:

        for key in keys:

            value = positive(
                source.get(
                    key
                )
            )

            if value > ZERO:
                return value

    return default


def extract_system_voltage(
    system_voltage: Any = None,
    voltage_result: Optional[Dict[str, Any]] = None,
    battery_result: Optional[Dict[str, Any]] = None,
) -> Decimal:
    """
    Extract the canonical battery/system voltage.

    Priority:

        explicit system_voltage
        Phase 2 result
        Phase 3 result
    """

    direct = positive(
        system_voltage
    )

    if direct > ZERO:
        return direct

    sources = []

    if isinstance(
        voltage_result,
        dict,
    ):

        sources.extend(
            [
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
        )

        selected = voltage_result.get(
            "selected"
        )

        if isinstance(
            selected,
            dict,
        ):
            sources.extend(
                [
                    selected.get(
                        "system_voltage"
                    ),
                    selected.get(
                        "voltage"
                    ),
                ]
            )

    if isinstance(
        battery_result,
        dict,
    ):

        sources.append(
            battery_result.get(
                "system_voltage"
            )
        )

        required = battery_result.get(
            "required"
        )

        if isinstance(
            required,
            dict,
        ):

            sources.extend(
                [
                    required.get(
                        "system_voltage"
                    ),
                    required.get(
                        "battery_voltage"
                    ),
                ]
            )

        selected = battery_result.get(
            "selected"
        )

        if isinstance(
            selected,
            dict,
        ):

            sources.extend(
                [
                    selected.get(
                        "system_voltage"
                    ),
                    selected.get(
                        "battery_voltage"
                    ),
                    selected.get(
                        "bank_voltage"
                    ),
                ]
            )

    for value in sources:

        number = positive(
            value
        )

        if number > ZERO:
            return number

    return ZERO


# ==================================================================
# PV ARRAY EXTRACTION
# ==================================================================

def extract_pv_array(
    panel_result: Optional[Dict[str, Any]],
) -> Dict[str, Decimal]:
    """
    Extract the actual selected PV array from Phase 4.

    Expected values:

        array_voltage
        array_current
        installed_power
        array_isc
        corrected_voc

    The engine supports several synonymous keys because the result
    contract contains both engineering and presentation layers.
    """

    array_voltage = extract_array_value(
        panel_result,
        (
            "array_voltage",
            "operating_voltage",
            "mppt_voltage",
            "string_vmp",
        ),
    )

    array_current = extract_array_value(
        panel_result,
        (
            "array_current",
            "operating_current",
            "mppt_current",
            "string_current",
        ),
    )

    array_power = extract_array_value(
        panel_result,
        (
            "installed_power",
            "array_power",
            "pv_power",
            "total_pv_power",
        ),
    )

    array_isc = extract_array_value(
        panel_result,
        (
            "array_isc",
            "isc",
            "short_circuit_current",
        ),
    )

    corrected_voc = extract_array_value(
        panel_result,
        (
            "corrected_voc",
            "array_voc",
            "maximum_voc",
            "cold_voc",
            "max_voc",
        ),
    )

    # --------------------------------------------------------------
    # If power is not explicitly available, derive it from V × I.
    # --------------------------------------------------------------

    if (
        array_power <= ZERO
        and
        array_voltage > ZERO
        and
        array_current > ZERO
    ):

        array_power = (
            array_voltage
            *
            array_current
        )

    # --------------------------------------------------------------
    # If array current is unavailable, derive it from P / V.
    # --------------------------------------------------------------

    if (
        array_current <= ZERO
        and
        array_power > ZERO
        and
        array_voltage > ZERO
    ):

        array_current = (
            array_power
            /
            array_voltage
        )

    return {
        "array_voltage": array_voltage,

        "array_current": array_current,

        "array_power": array_power,

        "array_isc": array_isc,

        "corrected_voc": corrected_voc,
    }


# ==================================================================
# SYSTEM VOLTAGE NORMALIZATION
# ==================================================================

def normalize_nominal_voltage(
    value: Any,
) -> Decimal:
    """
    Normalize actual lithium nominal voltage into the controller's
    nominal battery-voltage class.

        12.8 V -> 12 V
        25.6 V -> 24 V
        51.2 V -> 48 V

    Other values remain unchanged.

    This is necessary because a battery can have a chemistry-specific
    nominal voltage while the controller catalogue is classified
    using the standard 12/24/48/etc. system class.
    """

    voltage = positive(
        value
    )

    if voltage <= ZERO:
        return ZERO

    mapping = {
        Decimal("12.8"): Decimal("12"),
        Decimal("25.6"): Decimal("24"),
        Decimal("51.2"): Decimal("48"),
    }

    for actual, nominal in mapping.items():

        if abs(
            voltage - actual
        ) <= Decimal("0.15"):

            return nominal

    return voltage


# ==================================================================
# CONTROLLER REQUIREMENT CALCULATION
# ==================================================================

def calculate_controller_requirement(
    system_voltage: Any,
    panel_result: Optional[Dict[str, Any]],
    safety_factor: Any = DEFAULT_CONTROLLER_SAFETY_FACTOR,
    pv_voltage_margin: Any = DEFAULT_PV_VOLTAGE_MARGIN,
    pv_current_margin: Any = DEFAULT_PV_CURRENT_MARGIN,
    charge_current_margin: Any = DEFAULT_CHARGE_CURRENT_MARGIN,
) -> Dict[str, Any]:
    """
    Calculate the complete MPPT controller requirement.

    Engineering basis
    ------------------

    PV operating current:

        array_current

    PV design current:

        array_current × current margin

    Battery charging current:

        array_power / system_voltage

    Required charge-current capacity:

        charging current × charge-current margin

    Required PV voltage rating:

        maximum corrected Voc × voltage margin

    Required PV current rating:

        array Isc/current design basis × current margin

    Important
    ---------
    The controller must be checked against the actual PV array
    configuration, not merely the nominal PV wattage.
    """

    warnings = []

    # ==============================================================
    # SYSTEM VOLTAGE
    # ==============================================================

    raw_system_voltage = positive(
        system_voltage
    )

    if raw_system_voltage <= ZERO:

        return failure_result(
            message=(
                "System voltage must be greater than zero."
            ),
            warnings=[
                (
                    "Phase 6 cannot size the charge controller "
                    "without a valid battery/system voltage."
                )
            ],
        )

    controller_voltage = normalize_nominal_voltage(
        raw_system_voltage
    )

    if controller_voltage <= ZERO:

        return failure_result(
            message=(
                "The controller battery voltage could not be determined."
            ),
            warnings=[
                "Invalid system voltage."
            ],
        )

    # ==============================================================
    # PV ARRAY
    # ==============================================================

    array = extract_pv_array(
        panel_result
    )

    array_voltage = array[
        "array_voltage"
    ]

    array_current = array[
        "array_current"
    ]

    array_power = array[
        "array_power"
    ]

    array_isc = array[
        "array_isc"
    ]

    corrected_voc = array[
        "corrected_voc"
    ]

    if array_voltage <= ZERO:

        return failure_result(
            message=(
                "PV array voltage is missing."
            ),
            warnings=[
                (
                    "Phase 4 must provide the actual PV array "
                    "operating voltage before Phase 6 can select "
                    "an MPPT controller."
                )
            ],
        )

    if array_power <= ZERO:

        return failure_result(
            message=(
                "PV array power is missing."
            ),
            warnings=[
                (
                    "Phase 4 must provide the installed PV array "
                    "power before Phase 6 can size the controller."
                )
            ],
        )

    if array_current <= ZERO:

        return failure_result(
            message=(
                "PV array current is missing."
            ),
            warnings=[
                (
                    "Phase 4 must provide PV array operating current."
                )
            ],
        )

    # ==============================================================
    # FACTORS
    # ==============================================================

    safety = normalize_factor(
        safety_factor,
        DEFAULT_CONTROLLER_SAFETY_FACTOR,
    )

    voltage_margin = normalize_factor(
        pv_voltage_margin,
        DEFAULT_PV_VOLTAGE_MARGIN,
    )

    current_margin = normalize_factor(
        pv_current_margin,
        DEFAULT_PV_CURRENT_MARGIN,
    )

    charge_margin = normalize_factor(
        charge_current_margin,
        DEFAULT_CHARGE_CURRENT_MARGIN,
    )

    # Never allow factors below unity.
    safety = max(
        safety,
        ONE,
    )

    voltage_margin = max(
        voltage_margin,
        ONE,
    )

    current_margin = max(
        current_margin,
        ONE,
    )

    charge_margin = max(
        charge_margin,
        ONE,
    )

    # ==============================================================
    # PV MAXIMUM VOLTAGE
    # ==============================================================

    if corrected_voc > ZERO:

        required_pv_voltage = (
            corrected_voc
            *
            voltage_margin
        )

    else:

        # We cannot pretend Vmp is Voc.
        #
        # If Phase 4 did not provide corrected Voc, use the array
        # operating voltage as a minimum engineering value and
        # explicitly warn the user.
        required_pv_voltage = (
            array_voltage
            *
            voltage_margin
        )

        warnings.append(
            (
                "Corrected PV open-circuit voltage (Voc) was not "
                "provided by Phase 4. Controller voltage selection "
                "therefore uses the array operating voltage as a "
                "fallback. A verified cold-weather Voc should be "
                "provided for final engineering approval."
            )
        )

    # ==============================================================
    # PV CURRENT
    # ==============================================================

    current_basis = (
        array_isc
        if array_isc > ZERO
        else array_current
    )

    required_pv_current = (
        current_basis
        *
        current_margin
    )

    # ==============================================================
    # BATTERY CHARGING CURRENT
    # ==============================================================

    estimated_charge_current = (
        array_power
        /
        controller_voltage
    )

    required_charge_current = (
        estimated_charge_current
        *
        charge_margin
    )

    # ==============================================================
    # REQUIRED CONTROLLER POWER
    # ==============================================================

    minimum_controller_power = (
        controller_voltage
        *
        required_charge_current
    )

    # ==============================================================
    # CONTROLLER COUNT
    # ==============================================================

    # One controller can be selected only if its charge current,
    # PV voltage and PV current limits are sufficient.
    #
    # For engineering purposes, the current requirement determines
    # the minimum quantity.
    #
    # The actual database product is selected later.
    minimum_controller_quantity = ceil_decimal(
        required_charge_current
        /
        max(
            required_charge_current,
            ONE,
        )
    )

    # This is intentionally 1 at the engineering stage.
    #
    # The selection engine determines whether one controller is
    # sufficient and, if not, how many identical controllers are
    # required.
    minimum_controller_quantity = max(
        1,
        minimum_controller_quantity,
    )

    # ==============================================================
    # WARNINGS
    # ==============================================================

    if array_voltage < controller_voltage:

        warnings.append(
            (
                "PV array operating voltage is close to the battery "
                "system voltage. Confirm that the selected MPPT "
                "controller has sufficient tracking headroom."
            )
        )

    if required_pv_current > Decimal("100"):

        warnings.append(
            (
                "High PV current requirement detected. Multiple "
                "MPPT controllers or a higher-current controller "
                "may be required."
            )
        )

    if array_power > Decimal("10000"):

        warnings.append(
            (
                "Large PV array detected. Multiple MPPT controllers "
                "or a multi-MPPT architecture may be preferable."
            )
        )

    if array_power / controller_voltage > Decimal("100"):

        warnings.append(
            (
                "High battery-side charging current detected. "
                "Verify battery bank charge-current limits and "
                "consider multiple charge controllers."
            )
        )

    # ==============================================================
    # RESULT
    # ==============================================================

    requirement = {
        "battery_voltage": controller_voltage,

        "system_voltage": raw_system_voltage,

        "minimum_pv_voltage": (
            required_pv_voltage
        ),

        "minimum_pv_current": (
            required_pv_current
        ),

        "minimum_charge_current": (
            required_charge_current
        ),

        "minimum_pv_power": (
            array_power
            *
            safety
        ),

        "minimum_controller_power": (
            minimum_controller_power
        ),

        "minimum_controller_quantity": (
            minimum_controller_quantity
        ),

        "array_voltage": array_voltage,

        "array_current": array_current,

        "array_isc": array_isc,

        "array_power": array_power,

        "corrected_voc": corrected_voc,

        "estimated_charge_current": (
            estimated_charge_current
        ),

        "safety_factor": safety,

        "pv_voltage_margin": voltage_margin,

        "pv_current_margin": current_margin,

        "charge_current_margin": charge_margin,
    }

    return {
        "success": True,

        "status": "calculated",

        "requirement": serialize_requirement(
            requirement
        ),

        "design": {
            "system_voltage": output_number(
                raw_system_voltage
            ),

            "controller_battery_voltage": output_number(
                controller_voltage
            ),

            "array_voltage": output_number(
                array_voltage
            ),

            "array_current": output_number(
                array_current
            ),

            "array_isc": output_number(
                array_isc
            ),

            "array_power": output_number(
                array_power
            ),

            "corrected_voc": output_number(
                corrected_voc
            ),

            "estimated_charge_current": output_number(
                estimated_charge_current
            ),

            "required_charge_current": output_number(
                required_charge_current
            ),

            "required_pv_voltage": output_number(
                required_pv_voltage
            ),

            "required_pv_current": output_number(
                required_pv_current
            ),

            "minimum_controller_power": output_number(
                minimum_controller_power
            ),
        },

        "warnings": warnings,

        "messages": [
            (
                "Charge controller engineering requirements "
                "successfully calculated."
            )
        ],

        "message": (
            "Charge controller engineering requirements "
            "successfully calculated."
        ),

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ==================================================================
# REQUIREMENT VALIDATION
# ==================================================================

def validate_controller_requirement(
    requirement: Dict[str, Any],
) -> List[str]:
    """
    Validate controller engineering requirements.
    """

    errors = []

    required_fields = {
        "battery_voltage": "battery/system voltage",
        "minimum_pv_voltage": "minimum PV voltage",
        "minimum_pv_current": "minimum PV current",
        "minimum_charge_current": "minimum charge current",
        "minimum_pv_power": "minimum PV power",
        "minimum_controller_power": "minimum controller power",
    }

    for key, label in required_fields.items():

        if positive(
            requirement.get(
                key
            )
        ) <= ZERO:

            errors.append(
                f"{label.capitalize()} must be greater than zero."
            )

    return errors


# ==================================================================
# SERIALIZATION
# ==================================================================

def serialize_requirement(
    requirement: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert engineering requirement into JSON-safe values.
    """

    return {
        "battery_voltage": output_number(
            requirement.get(
                "battery_voltage",
                ZERO,
            )
        ),

        "system_voltage": output_number(
            requirement.get(
                "system_voltage",
                ZERO,
            )
        ),

        "minimum_pv_voltage": output_number(
            requirement.get(
                "minimum_pv_voltage",
                ZERO,
            )
        ),

        "minimum_pv_current": output_number(
            requirement.get(
                "minimum_pv_current",
                ZERO,
            )
        ),

        "minimum_charge_current": output_number(
            requirement.get(
                "minimum_charge_current",
                ZERO,
            )
        ),

        "minimum_pv_power": output_number(
            requirement.get(
                "minimum_pv_power",
                ZERO,
            )
        ),

        "minimum_controller_power": output_number(
            requirement.get(
                "minimum_controller_power",
                ZERO,
            )
        ),

        "minimum_controller_quantity": int(
            requirement.get(
                "minimum_controller_quantity",
                1,
            )
        ),

        "array_voltage": output_number(
            requirement.get(
                "array_voltage",
                ZERO,
            )
        ),

        "array_current": output_number(
            requirement.get(
                "array_current",
                ZERO,
            )
        ),

        "array_isc": output_number(
            requirement.get(
                "array_isc",
                ZERO,
            )
        ),

        "array_power": output_number(
            requirement.get(
                "array_power",
                ZERO,
            )
        ),

        "corrected_voc": output_number(
            requirement.get(
                "corrected_voc",
                ZERO,
            )
        ),

        "estimated_charge_current": output_number(
            requirement.get(
                "estimated_charge_current",
                ZERO,
            )
        ),

        "safety_factor": output_number(
            requirement.get(
                "safety_factor",
                DEFAULT_CONTROLLER_SAFETY_FACTOR,
            ),
            places=4,
        ),

        "pv_voltage_margin": output_number(
            requirement.get(
                "pv_voltage_margin",
                DEFAULT_PV_VOLTAGE_MARGIN,
            ),
            places=4,
        ),

        "pv_current_margin": output_number(
            requirement.get(
                "pv_current_margin",
                DEFAULT_PV_CURRENT_MARGIN,
            ),
            places=4,
        ),

        "charge_current_margin": output_number(
            requirement.get(
                "charge_current_margin",
                DEFAULT_CHARGE_CURRENT_MARGIN,
            ),
            places=4,
        ),
    }


# ==================================================================
# FAILURE CONTRACT
# ==================================================================

def failure_result(
    message: str,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Standard Phase 6 engineering failure.

    Every expected result key exists so downstream code can safely
    inspect the result without causing KeyError/NoneType crashes.
    """

    return {
        "success": False,

        "status": "error",

        "requirement": {},

        "design": {},

        "selected": None,

        "alternatives": [],

        "closest": [],

        "candidates": [],

        "warnings": (
            warnings
            if warnings
            else [
                message
            ]
        ),

        "messages": [],

        "message": message,

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ==================================================================
# PUBLIC ALIASES
# ==================================================================

run_controller_engine = calculate_controller_requirement