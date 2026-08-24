"""
solar/services/inverter_engine.py

PHASE 5
INVERTER ENGINE

This module is the single source of truth for inverter engineering.

Responsibilities
----------------
1. Read the canonical system voltage from Phase 2 / Phase 3.
2. Read the actual operating load from Phase 1.
3. Read surge demand from Phase 1 when available.
4. Calculate the minimum continuous inverter requirement.
5. Calculate the minimum surge requirement.
6. Select a compatible inverter from the database.
7. Validate:
       - DC/system voltage
       - continuous power
       - surge power
       - AC output voltage
       - phase
       - frequency
8. Rank compatible alternatives.
9. Provide a safe "no inverter found" result.
10. Provide closest available products WITHOUT pretending they
    are engineering-compatible.
11. Return a stable result contract for later engines.

Important
---------
The engine never silently substitutes an incompatible inverter.

If no suitable inverter exists:

    success = False
    selected = None

but the engine STILL returns a complete structured result.

The application can therefore display a proper engineering warning
instead of crashing because selected["rated_power"] does not exist.

All engineering arithmetic uses Decimal.

Database FloatField values are converted to Decimal immediately.

This module does NOT:
    - size batteries
    - size PV
    - size charge controllers
    - size cables
    - size protection
    - calculate final pricing
"""

from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
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

ENGINE_NAME = "Inverter Engineering Engine"
ENGINE_VERSION = "5.0.0"


# ==================================================================
# DECIMAL CONSTANTS
# ==================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
THOUSAND = Decimal("1000")


# ==================================================================
# DEFAULT DESIGN VALUES
# ==================================================================

DEFAULT_CONTINUOUS_MARGIN = Decimal("1.25")

DEFAULT_SURGE_MARGIN = Decimal("1.00")

DEFAULT_INVERTER_EFFICIENCY = Decimal("0.95")

DEFAULT_OUTPUT_VOLTAGE = Decimal("230")

DEFAULT_FREQUENCY = Decimal("50")

DEFAULT_PHASE = "single_phase"

DEFAULT_POWER_FACTOR = Decimal("1.00")

# Minimum useful inverter loading requirement.
MINIMUM_LOADING_RATIO = Decimal("0.25")


# ==================================================================
# SAFE DECIMAL CONVERSION
# ==================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert a value to Decimal.

    Float values are converted through str() to prevent binary
    floating-point artefacts from entering engineering calculations.
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
    Return a positive Decimal or default.
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
    Return a non-negative Decimal.
    """

    result = to_decimal(
        value,
        default,
    )

    if result < ZERO:
        return ZERO

    return result


def normalize_factor(
    value: Any,
    default: Decimal,
) -> Decimal:
    """
    Normalize percentage/factor input.

    Examples:

        0.95 -> 0.95
        95   -> 0.95

    Values above 100 are interpreted as percentages.
    """

    result = to_decimal(
        value,
        default,
    )

    if result <= ZERO:
        return default

    if result > HUNDRED:
        result = result / HUNDRED

    if result > ONE:
        return default

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
    Convert Decimal to JSON-safe number.
    """

    number = round_decimal(
        value,
        places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ==================================================================
# TEXT NORMALIZATION
# ==================================================================

def normalize_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Normalize textual database/user input.
    """

    if value is None:
        return default

    return str(
        value
    ).strip()


# ==================================================================
# SYSTEM VOLTAGE NORMALIZATION
# ==================================================================

def normalize_system_voltage(
    value: Any,
) -> Decimal:
    """
    Normalize the system voltage used for inverter matching.

    The system voltage is allowed to be:

        12
        12.8
        24
        25.6
        48
        51.2
        96
        192
        etc.

    Lithium nominal voltages such as 12.8 / 25.6 / 51.2 V are
    mapped to the corresponding inverter nominal class:

        12.8 -> 12
        25.6 -> 24
        51.2 -> 48

    Other values remain unchanged.

    This is important because the inverter database stores nominal
    DC voltage, while the battery may store actual nominal chemistry
    voltage.
    """

    voltage = positive(
        value
    )

    if voltage <= ZERO:
        return ZERO

    nominal_classes = {
        Decimal("12.8"): Decimal("12"),
        Decimal("25.6"): Decimal("24"),
        Decimal("51.2"): Decimal("48"),
    }

    for actual, nominal in nominal_classes.items():

        if abs(
            voltage - actual
        ) <= Decimal("0.15"):

            return nominal

    return voltage


def voltage_compatible(
    inverter_voltage: Any,
    system_voltage: Any,
) -> bool:
    """
    Determine whether an inverter DC voltage is compatible with
    the canonical system voltage.
    """

    inverter = normalize_system_voltage(
        inverter_voltage
    )

    system = normalize_system_voltage(
        system_voltage
    )

    if inverter <= ZERO or system <= ZERO:
        return False

    return inverter == system


# ==================================================================
# RESULT EXTRACTION
# ==================================================================

def extract_system_voltage(
    voltage_result: Optional[Dict[str, Any]],
    battery_result: Optional[Dict[str, Any]] = None,
) -> Decimal:
    """
    Extract the canonical system voltage.

    Priority:

        Phase 2 system_voltage
        Phase 3 system_voltage
        Phase 3 required.system_voltage
    """

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
        sources.extend(
            [
                battery_result.get(
                    "system_voltage"
                ),
            ]
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
                        "bank_voltage"
                    ),
                ]
            )

    for value in sources:

        voltage = positive(
            value
        )

        if voltage > ZERO:
            return voltage

    return ZERO

def extract_running_load(
    load_result: Dict[str, Any],
) -> Decimal:

    if not isinstance(load_result, dict):
        return ZERO

    calculations = load_result.get("calculations")

    if isinstance(calculations, dict):

        # Phase 1 canonical running/design load
        value = to_decimal(
            calculations.get("peak_design_load_w")
        )

        if value > ZERO:
            return value

        # Fallback
        value = to_decimal(
            calculations.get("running_peak_load_w")
        )

        if value > ZERO:
            return value

    selected = load_result.get("selected")

    if isinstance(selected, dict):

        value = to_decimal(
            selected.get("peak_load_w")
        )

        if value > ZERO:
            return value

    # Legacy flat-result compatibility
    for key in (
        "peak_design_load_w",
        "running_peak_load_w",
        "peak_load_w",
        "load_w",
        "load_watts",
    ):
        value = to_decimal(
            load_result.get(key)
        )

        if value > ZERO:
            return value

    return ZERO

def extract_surge_load(
    load_result: Dict[str, Any],
) -> Decimal:

    if not isinstance(load_result, dict):
        return ZERO

    calculations = load_result.get("calculations")

    if isinstance(calculations, dict):

        value = to_decimal(
            calculations.get("surge_peak_load_w")
        )

        if value > ZERO:
            return value

    selected = load_result.get("selected")

    if isinstance(selected, dict):

        value = to_decimal(
            selected.get("surge_load_w")
        )

        if value > ZERO:
            return value

    # Legacy flat-result compatibility
    for key in (
        "surge_peak_load_w",
        "surge_load_w",
        "surge_watts",
    ):
        value = to_decimal(
            load_result.get(key)
        )

        if value > ZERO:
            return value

    return ZERO

# ==================================================================
# POWER REQUIREMENT ENGINE
# ==================================================================

def calculate_inverter_requirement(
    running_load_w: Any,
    surge_load_w: Any,
    continuous_margin: Any = DEFAULT_CONTINUOUS_MARGIN,
    surge_margin: Any = DEFAULT_SURGE_MARGIN,
) -> Dict[str, Any]:
    """
    Calculate the minimum inverter requirements.

    Continuous requirement:

        running load × continuous margin

    Surge requirement:

        actual surge load × surge margin

    IMPORTANT:

    We do NOT automatically multiply the user's already-calculated
    surge load by another arbitrary appliance surge factor.

    Phase 1 owns load/surge engineering.

    Phase 5 only applies the inverter design margin.
    """

    running_load = positive(
        running_load_w
    )

    surge_load = positive(
        surge_load_w
    )

    if surge_load < running_load:
        surge_load = running_load

    continuous_factor = positive(
        continuous_margin,
        DEFAULT_CONTINUOUS_MARGIN,
    )

    surge_factor = positive(
        surge_margin,
        DEFAULT_SURGE_MARGIN,
    )

    minimum_continuous_power = (
        running_load
        * continuous_factor
    )

    minimum_surge_power = (
        surge_load
        * surge_factor
    )

    # Surge capability must never be lower than continuous
    # operating requirement.
    if (
        minimum_surge_power
        <
        minimum_continuous_power
    ):
        minimum_surge_power = (
            minimum_continuous_power
        )

    return {
        "running_load_w": running_load,

        "running_load_kw": (
            running_load
            /
            THOUSAND
        ),

        "surge_load_w": surge_load,

        "surge_load_kw": (
            surge_load
            /
            THOUSAND
        ),

        "continuous_margin": continuous_factor,

        "surge_margin": surge_factor,

        "minimum_rated_power_w": (
            minimum_continuous_power
        ),

        "minimum_rated_power_kw": (
            minimum_continuous_power
            /
            THOUSAND
        ),

        "minimum_surge_power_w": (
            minimum_surge_power
        ),

        "minimum_surge_power_kw": (
            minimum_surge_power
            /
            THOUSAND
        ),
    }


# ==================================================================
# INVERTER MODEL NORMALIZATION
# ==================================================================

def normalize_inverter_record(
    inverter: Any,
) -> Dict[str, Any]:
    """
    Convert a Django Inverter instance or dictionary into the
    internal representation.
    """

    if isinstance(
        inverter,
        dict,
    ):
        getter = inverter.get

    else:
        getter = (
            lambda key, default=None:
            getattr(
                inverter,
                key,
                default,
            )
        )

    return {
        "id": getter(
            "id"
        ),

        "brand": normalize_text(
            getter(
                "brand"
            )
        ),

        "model": normalize_text(
            getter(
                "model"
            )
        ),

        "rated_power": to_decimal(
            getter(
                "rated_power",
                0,
            )
        ),

        "surge_power": to_decimal(
            getter(
                "surge_power",
                0,
            )
        ),

        "output_voltage": to_decimal(
            getter(
                "output_voltage",
                DEFAULT_OUTPUT_VOLTAGE,
            )
        ),

        "phase": normalize_text(
            getter(
                "phase",
                DEFAULT_PHASE,
            ),
            DEFAULT_PHASE,
        ),

        "frequency": to_decimal(
            getter(
                "frequency",
                DEFAULT_FREQUENCY,
            )
        ),

        "dc_voltage": to_decimal(
            getter(
                "dc_voltage",
                0,
            )
        ),

        "efficiency": normalize_factor(
            getter(
                "efficiency",
                DEFAULT_INVERTER_EFFICIENCY,
            ),
            DEFAULT_INVERTER_EFFICIENCY,
        ),

        "hybrid": bool(
            getter(
                "hybrid",
                False,
            )
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


# ==================================================================
# INVERTER VALIDATION
# ==================================================================

def validate_inverter_record(
    inverter: Dict[str, Any],
) -> List[str]:
    """
    Validate database inverter data before using it.
    """

    errors = []

    if inverter[
        "rated_power"
    ] <= ZERO:

        errors.append(
            "Rated inverter power must be greater than zero."
        )

    if inverter[
        "surge_power"
    ] <= ZERO:

        errors.append(
            "Inverter surge power must be greater than zero."
        )

    if inverter[
        "dc_voltage"
    ] <= ZERO:

        errors.append(
            "Inverter DC voltage must be greater than zero."
        )

    if (
        inverter[
            "surge_power"
        ]
        <
        inverter[
            "rated_power"
        ]
    ):

        errors.append(
            "Inverter surge power cannot be lower than rated power."
        )

    if inverter[
        "output_voltage"
    ] <= ZERO:

        errors.append(
            "Inverter AC output voltage must be greater than zero."
        )

    if inverter[
        "frequency"
    ] <= ZERO:

        errors.append(
            "Inverter frequency must be greater than zero."
        )

    return errors


# ==================================================================
# AC OUTPUT COMPATIBILITY
# ==================================================================

def output_voltage_compatible(
    inverter_voltage: Any,
    required_voltage: Any,
    tolerance: Decimal = Decimal("5"),
) -> bool:
    """
    Determine AC output-voltage compatibility.

    Default tolerance:

        ±5 V

    This allows normal 220/230 V database variation without
    accepting obviously different output classes.
    """

    inverter = positive(
        inverter_voltage
    )

    required = positive(
        required_voltage,
        DEFAULT_OUTPUT_VOLTAGE,
    )

    if inverter <= ZERO or required <= ZERO:
        return False

    return (
        abs(
            inverter
            -
            required
        )
        <= tolerance
    )


def phase_compatible(
    inverter_phase: Any,
    required_phase: Any,
) -> bool:
    """
    Compare inverter phase with required phase.

    If no phase requirement is supplied, any valid phase is allowed.

    Supported values:

        single_phase
        three_phase
    """

    required = normalize_text(
        required_phase
    ).lower()

    inverter = normalize_text(
        inverter_phase,
        DEFAULT_PHASE,
    ).lower()

    if not required:
        return True

    return inverter == required


def frequency_compatible(
    inverter_frequency: Any,
    required_frequency: Any,
    tolerance: Decimal = Decimal("1"),
) -> bool:
    """
    Compare AC frequency.
    """

    inverter = positive(
        inverter_frequency
    )

    required = positive(
        required_frequency,
        DEFAULT_FREQUENCY,
    )

    if inverter <= ZERO or required <= ZERO:
        return False

    return (
        abs(
            inverter
            -
            required
        )
        <= tolerance
    )


# ==================================================================
# SINGLE INVERTER EVALUATION
# ==================================================================

def evaluate_inverter(
    inverter: Any,
    required: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluate one inverter against the complete engineering
    requirement.
    """

    record = normalize_inverter_record(
        inverter
    )

    validation_errors = (
        validate_inverter_record(
            record
        )
    )

    required_dc_voltage = normalize_system_voltage(
        required.get(
            "dc_voltage"
        )
    )

    minimum_rated_power = positive(
        required.get(
            "minimum_rated_power_w"
        )
    )

    minimum_surge_power = positive(
        required.get(
            "minimum_surge_power_w"
        )
    )

    required_output_voltage = positive(
        required.get(
            "output_voltage",
            DEFAULT_OUTPUT_VOLTAGE,
        ),
        DEFAULT_OUTPUT_VOLTAGE,
    )

    required_phase = normalize_text(
        required.get(
            "phase"
        )
    )

    required_frequency = positive(
        required.get(
            "frequency",
            DEFAULT_FREQUENCY,
        ),
        DEFAULT_FREQUENCY,
    )

    checks = {
        "dc_voltage": voltage_compatible(
            record[
                "dc_voltage"
            ],
            required_dc_voltage,
        ),

        "continuous_power": (
            record[
                "rated_power"
            ]
            >=
            minimum_rated_power
        ),

        "surge_power": (
            record[
                "surge_power"
            ]
            >=
            minimum_surge_power
        ),

        "output_voltage": output_voltage_compatible(
            record[
                "output_voltage"
            ],
            required_output_voltage,
        ),

        "phase": phase_compatible(
            record[
                "phase"
            ],
            required_phase,
        ),

        "frequency": frequency_compatible(
            record[
                "frequency"
            ],
            required_frequency,
        ),
    }

    compatible = (
        not validation_errors
        and
        all(
            checks.values()
        )
    )

    failures = []

    if validation_errors:
        failures.extend(
            validation_errors
        )

    if not checks[
        "dc_voltage"
    ]:
        failures.append(
            (
                "DC voltage mismatch: "
                f"inverter={output_number(record['dc_voltage'])} V, "
                f"required={output_number(required_dc_voltage)} V."
            )
        )

    if not checks[
        "continuous_power"
    ]:
        failures.append(
            (
                "Insufficient continuous power: "
                f"inverter={output_number(record['rated_power'])} W, "
                f"required={output_number(minimum_rated_power)} W."
            )
        )

    if not checks[
        "surge_power"
    ]:
        failures.append(
            (
                "Insufficient surge power: "
                f"inverter={output_number(record['surge_power'])} W, "
                f"required={output_number(minimum_surge_power)} W."
            )
        )

    if not checks[
        "output_voltage"
    ]:
        failures.append(
            (
                "AC output-voltage mismatch: "
                f"inverter={output_number(record['output_voltage'])} V, "
                f"required≈{output_number(required_output_voltage)} V."
            )
        )

    if not checks[
        "phase"
    ]:
        failures.append(
            (
                "Phase mismatch: "
                f"inverter={record['phase']}, "
                f"required={required_phase}."
            )
        )

    if not checks[
        "frequency"
    ]:
        failures.append(
            (
                "Frequency mismatch: "
                f"inverter={output_number(record['frequency'])} Hz, "
                f"required={output_number(required_frequency)} Hz."
            )
        )

    # --------------------------------------------------------------
    # SURPLUS
    # --------------------------------------------------------------

    continuous_surplus = (
        record[
            "rated_power"
        ]
        -
        minimum_rated_power
    )

    surge_surplus = (
        record[
            "surge_power"
        ]
        -
        minimum_surge_power
    )

    # --------------------------------------------------------------
    # UTILIZATION
    # --------------------------------------------------------------

    utilization = (
        minimum_rated_power
        /
        record[
            "rated_power"
        ]
        if record[
            "rated_power"
        ] > ZERO
        else ZERO
    )

    # --------------------------------------------------------------
    # SCORE
    # --------------------------------------------------------------

    score = calculate_inverter_score(
        record=record,
        required=required,
        continuous_surplus=continuous_surplus,
        surge_surplus=surge_surplus,
        utilization=utilization,
    )

    return {
        "compatible": compatible,

        "panel": None,

        "inverter": record,

        "checks": checks,

        "failures": failures,

        "continuous_surplus_w": continuous_surplus,

        "surge_surplus_w": surge_surplus,

        "utilization_ratio": utilization,

        "score": score,
    }


# ==================================================================
# INVERTER SCORING
# ==================================================================

def calculate_inverter_score(
    record: Dict[str, Any],
    required: Dict[str, Any],
    continuous_surplus: Decimal,
    surge_surplus: Decimal,
    utilization: Decimal,
) -> Decimal:
    """
    Rank compatible inverters.

    The engine prefers:

        1. electrically compatible products
        2. appropriate capacity
        3. good surge margin
        4. reasonable utilization
        5. better efficiency
        6. lower cost

    It does NOT simply choose the cheapest inverter.
    """

    score = Decimal("100")

    minimum_rated = positive(
        required.get(
            "minimum_rated_power_w"
        )
    )

    # --------------------------------------------------------------
    # Capacity oversizing
    # --------------------------------------------------------------

    if minimum_rated > ZERO:

        oversize_ratio = (
            record[
                "rated_power"
            ]
            /
            minimum_rated
        )

        if oversize_ratio <= Decimal("1.15"):
            score += Decimal("20")

        elif oversize_ratio <= Decimal("1.30"):
            score += Decimal("16")

        elif oversize_ratio <= Decimal("1.50"):
            score += Decimal("10")

        elif oversize_ratio <= Decimal("2.00"):
            score += Decimal("3")

        else:
            score -= Decimal("10")

    # --------------------------------------------------------------
    # Utilization
    # --------------------------------------------------------------

    if utilization >= Decimal("0.70"):
        score += Decimal("15")

    elif utilization >= Decimal("0.50"):
        score += Decimal("10")

    elif utilization >= Decimal("0.35"):
        score += Decimal("5")

    elif utilization < MINIMUM_LOADING_RATIO:
        score -= Decimal("10")

    # --------------------------------------------------------------
    # Efficiency
    # --------------------------------------------------------------

    efficiency = record[
        "efficiency"
    ]

    if efficiency >= Decimal("0.96"):
        score += Decimal("12")

    elif efficiency >= Decimal("0.95"):
        score += Decimal("10")

    elif efficiency >= Decimal("0.93"):
        score += Decimal("6")

    elif efficiency >= Decimal("0.90"):
        score += Decimal("2")

    else:
        score -= Decimal("5")

    # --------------------------------------------------------------
    # Surge capability
    # --------------------------------------------------------------

    minimum_surge = positive(
        required.get(
            "minimum_surge_power_w"
        )
    )

    if minimum_surge > ZERO:

        surge_ratio = (
            record[
                "surge_power"
            ]
            /
            minimum_surge
        )

        if surge_ratio >= Decimal("1.50"):
            score += Decimal("10")

        elif surge_ratio >= Decimal("1.25"):
            score += Decimal("7")

        elif surge_ratio >= Decimal("1.10"):
            score += Decimal("4")

    # --------------------------------------------------------------
    # Price
    # --------------------------------------------------------------

    if record[
        "price"
    ] > ZERO:

        if record[
            "price"
        ] <= Decimal("500000"):
            score += Decimal("5")

    # --------------------------------------------------------------
    # Hybrid capability
    # --------------------------------------------------------------

    if record[
        "hybrid"
    ]:
        score += Decimal("2")

    return max(
        ZERO,
        score,
    )


# ==================================================================
# SERIALIZATION
# ==================================================================

def serialize_inverter(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert evaluated inverter data into JSON-safe output.
    """

    record = result.get(
        "inverter",
        {},
    )

    return {
        "id": record.get(
            "id"
        ),

        "name": (
            f"{record.get('brand', '')} "
            f"{record.get('model', '')}"
        ).strip(),

        "brand": record.get(
            "brand",
            "",
        ),

        "model": record.get(
            "model",
            "",
        ),

        "rated_power": output_number(
            record.get(
                "rated_power",
                ZERO,
            )
        ),

        "rated_power_kw": output_number(
            to_decimal(
                record.get(
                    "rated_power",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "surge_power": output_number(
            record.get(
                "surge_power",
                ZERO,
            )
        ),

        "surge_power_kw": output_number(
            to_decimal(
                record.get(
                    "surge_power",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "dc_voltage": output_number(
            record.get(
                "dc_voltage",
                ZERO,
            )
        ),

        "output_voltage": output_number(
            record.get(
                "output_voltage",
                DEFAULT_OUTPUT_VOLTAGE,
            )
        ),

        "phase": record.get(
            "phase",
            DEFAULT_PHASE,
        ),

        "frequency": output_number(
            record.get(
                "frequency",
                DEFAULT_FREQUENCY,
            )
        ),

        "efficiency": output_number(
            record.get(
                "efficiency",
                DEFAULT_INVERTER_EFFICIENCY,
            ),
            places=4,
        ),

        "hybrid": bool(
            record.get(
                "hybrid",
                False,
            )
        ),

        "price": output_number(
            record.get(
                "price",
                ZERO,
            )
        ),

        "active": bool(
            record.get(
                "active",
                True,
            )
        ),

        "continuous_surplus_w": output_number(
            result.get(
                "continuous_surplus_w",
                ZERO,
            )
        ),

        "surge_surplus_w": output_number(
            result.get(
                "surge_surplus_w",
                ZERO,
            )
        ),

        "utilization_ratio": output_number(
            result.get(
                "utilization_ratio",
                ZERO,
            ),
            places=4,
        ),

        "score": output_number(
            result.get(
                "score",
                ZERO,
            )
        ),

        "checks": result.get(
            "checks",
            {},
        ),

        "failures": result.get(
            "failures",
            [],
        ),
    }


def serialize_candidate_list(
    results: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Serialize evaluated inverter candidates.
    """

    return [
        serialize_inverter(
            result
        )
        for result in results
    ]


# ==================================================================
# CLOSEST-INVERTER RANKING
# ==================================================================

def find_closest_inverters(
    evaluated: Iterable[Dict[str, Any]],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Find the closest products when no fully compatible inverter
    exists.

    IMPORTANT:

    These are NOT selected products.

    They are diagnostic suggestions only.

    A closest product is ranked according to the severity of its
    engineering deficiencies.
    """

    candidates = []

    for result in evaluated:

        inverter = result.get(
            "inverter",
            {},
        )

        failures = result.get(
            "failures",
            [],
        )

        checks = result.get(
            "checks",
            {},
        )

        # ----------------------------------------------------------
        # Voltage mismatch is treated as the most serious failure.
        # ----------------------------------------------------------

        voltage_penalty = (
            Decimal("0")
            if checks.get(
                "dc_voltage",
                False,
            )
            else Decimal("1000000")
        )

        rated_gap = max(
            ZERO,
            positive(
                0
            )
            -
            positive(
                result.get(
                    "continuous_surplus_w",
                    ZERO,
                )
            ),
        )

        surge_gap = max(
            ZERO,
            -positive(
                result.get(
                    "surge_surplus_w",
                    ZERO,
                )
            ),
        )

        failure_count = Decimal(
            len(
                failures
            )
        )

        # Smaller score is closer.
        distance_score = (
            voltage_penalty
            +
            rated_gap
            +
            surge_gap
            +
            (
                failure_count
                * Decimal("1000")
            )
        )

        candidates.append(
            (
                distance_score,
                result,
            )
        )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1].get(
                "inverter",
                {},
            ).get(
                "rated_power",
                ZERO,
            ),
        )
    )

    return [
        serialize_inverter(
            result
        )
        for _, result in candidates[
            :limit
        ]
    ]


# ==================================================================
# MAIN DATABASE SELECTION
# ==================================================================

def select_inverter(
    inverter_requirement: Optional[Dict[str, Any]] = None,
    inverters: Optional[Iterable[Any]] = None,
) -> Dict[str, Any]:
    """
    Select the best compatible inverter from the supplied database
    queryset/list.

    This function intentionally accepts the engineering requirement
    produced by Phase 5's requirement calculator.

    Example:

        requirement = {
            "dc_voltage": 48,
            "minimum_rated_power_w": 4200,
            "minimum_surge_power_w": 7000,
        }

    If `inverters` is omitted, the Django Inverter model is loaded
    lazily.
    """

    if not inverter_requirement:

        return failed_result(
            message=(
                "No inverter engineering requirement was supplied."
            ),
            warnings=[
                "Run the inverter requirement calculation first."
            ],
        )

    if inverters is None:

        try:

            from solar.models import Inverter

            inverters = (
                Inverter.objects
                .filter(
                    active=True
                )
            )

        except Exception as exc:

            return failed_result(
                message=(
                    "The inverter catalogue could not be loaded."
                ),
                warnings=[
                    (
                        "The inverter engine could not access "
                        "the Solar Inverter database."
                    ),
                    str(exc),
                ],
            )

    # --------------------------------------------------------------
    # Normalize requirement
    # --------------------------------------------------------------

    required = normalize_requirement(
        inverter_requirement
    )

    requirement_errors = validate_requirement(
        required
    )

    if requirement_errors:

        return failed_result(
            message=(
                "The inverter requirement is incomplete or invalid."
            ),
            warnings=requirement_errors,
            required=serialize_requirement(
                required
            ),
        )

    evaluated = []

    try:

        for inverter in inverters:

            record = normalize_inverter_record(
                inverter
            )

            if not record[
                "active"
            ]:
                continue

            result = evaluate_inverter(
                inverter=record,
                required=required,
            )

            evaluated.append(
                result
            )

    except Exception as exc:

        return failed_result(
            message=(
                "The inverter catalogue could not be evaluated."
            ),
            warnings=[
                (
                    "An unexpected error occurred while evaluating "
                    "the inverter catalogue."
                ),
                str(exc),
            ],
            required=serialize_requirement(
                required
            ),
        )

    compatible = [
        result
        for result in evaluated
        if result.get(
            "compatible",
            False,
        )
    ]

    # --------------------------------------------------------------
    # NO ACTIVE INVERTERS
    # --------------------------------------------------------------

    if not evaluated:

        return failed_result(
            message=(
                "No active inverter is available in the database."
            ),
            warnings=[
                (
                    "The calculator cannot select an inverter "
                    "until a compatible active inverter is added "
                    "to the inverter catalogue."
                )
            ],
            required=serialize_requirement(
                required
            ),
        )

    # --------------------------------------------------------------
    # SORT COMPATIBLE PRODUCTS
    # --------------------------------------------------------------
    # --------------------------------------------------------------
    # NO COMPATIBLE INVERTERS
    # --------------------------------------------------------------

    if not compatible:

        return failed_result(
            message=(
                "No compatible inverter was found in the database."
            ),
            warnings=[
                (
                    "Active inverters exist in the catalogue, but "
                    "none satisfy the required DC voltage, continuous "
                    "power, and surge power requirements."
                )
            ],
            required=serialize_requirement(
                required
            ),
        )

    compatible.sort(
        key=lambda result: (
            -result.get(
                "score",
                ZERO,
            ),
            result.get(
                "inverter",
                {},
            ).get(
                "rated_power",
                ZERO,
            ),
            result.get(
                "inverter",
                {},
            ).get(
                "price",
                ZERO,
            ),
        )
    )

    selected = compatible[
        0
    ]

    alternatives = compatible[
        1:6
    ]

    warnings = []

    selected_record = selected[
        "inverter"
    ]

    minimum_rated = required[
        "minimum_rated_power_w"
    ]

    if (
        selected_record[
            "rated_power"
        ]
        >
        minimum_rated
        * Decimal("1.50")
    ):

        warnings.append(
            (
                "The selected inverter is significantly larger "
                "than the calculated continuous requirement."
            )
        )

    if selected_record[
        "efficiency"
    ] < Decimal("0.90"):

        warnings.append(
            (
                "The selected inverter has an efficiency below 90%."
            )
        )

    if selected_record[
        "hybrid"
    ]:

        warnings.append(
            (
                "The selected inverter is a hybrid inverter."
            )
        )

    return {
        "success": True,

        "status": "selected",

        "required": serialize_requirement(
            required
        ),

        "selected": serialize_inverter(
            selected
        ),

        "alternatives": serialize_candidate_list(
            alternatives
        ),

        "closest": None,

        "candidates": serialize_candidate_list(
            evaluated
        ),

        "warnings": warnings,

        "messages": [
            (
                f"{selected_record['brand']} "
                f"{selected_record['model']} "
                "satisfies the inverter engineering requirements."
            )
        ],

        "message": (
            f"{selected_record['brand']} "
            f"{selected_record['model']} "
            "is the recommended inverter."
        ),

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ==================================================================
# COMPLETE PHASE 5 ENGINE
# ==================================================================

def calculate_inverter(
    load_result: Optional[Dict[str, Any]],
    voltage_result: Optional[Dict[str, Any]],
    battery_result: Optional[Dict[str, Any]] = None,
    inverters: Optional[Iterable[Any]] = None,
    continuous_margin: Any = DEFAULT_CONTINUOUS_MARGIN,
    surge_margin: Any = DEFAULT_SURGE_MARGIN,
    output_voltage: Any = DEFAULT_OUTPUT_VOLTAGE,
    phase: Optional[str] = None,
    frequency: Any = DEFAULT_FREQUENCY,
) -> Dict[str, Any]:
    """
    Complete Phase 5 public entry point.

    Inputs:

        load_result
            Phase 1 output.

        voltage_result
            Phase 2 output.

        battery_result
            Phase 3 output.

        inverters
            Active inverter catalogue.

    The engine:

        Phase 1
           ↓
        running/surge load
           ↓
        inverter requirement
           ↓
        Phase 2/3
           ↓
        system voltage
           ↓
        inverter catalogue
           ↓
        compatible inverter
    """

    warnings = []
    messages = []

    # ==============================================================
    # INPUT VALIDATION
    # ==============================================================

    if not isinstance(
        load_result,
        dict,
    ):

        return failed_result(
            message=(
                "Phase 5 cannot read the Phase 1 load-engine result."
            ),
            warnings=[
                "A valid load_result dictionary is required."
            ],
        )

    if not isinstance(
        voltage_result,
        dict,
    ):

        return failed_result(
            message=(
                "Phase 5 cannot read the Phase 2 voltage-engine result."
            ),
            warnings=[
                "A valid voltage_result dictionary is required."
            ],
        )

    # ==============================================================
    # EXTRACT LOAD
    # ==============================================================

    running_load = extract_running_load(
        load_result
    )

    surge_load = extract_surge_load(
        load_result
    )

    if running_load <= ZERO:

        return failed_result(
            message=(
                "No valid running load was supplied."
            ),
            warnings=[
                (
                    "The inverter cannot be sized because "
                    "Phase 1 did not provide a positive load value."
                )
            ],
        )

    if surge_load <= ZERO:

        surge_load = running_load

        warnings.append(
            (
                "No separate surge-load value was supplied by "
                "Phase 1. Running load was used as the minimum "
                "surge requirement."
            )
        )

    # ==============================================================
    # SYSTEM VOLTAGE
    # ==============================================================

    raw_system_voltage = extract_system_voltage(
        voltage_result=voltage_result,
        battery_result=battery_result,
    )

    if raw_system_voltage <= ZERO:

        return failed_result(
            message=(
                "No valid system voltage was supplied by "
                "Phase 2 or Phase 3."
            ),
            warnings=[
                (
                    "The inverter DC voltage cannot be determined."
                )
            ],
        )

    nominal_system_voltage = normalize_system_voltage(
        raw_system_voltage
    )

    # ==============================================================
    # AC OUTPUT REQUIREMENTS
    # ==============================================================

    required_output_voltage = positive(
        output_voltage,
        DEFAULT_OUTPUT_VOLTAGE,
    )

    required_frequency = positive(
        frequency,
        DEFAULT_FREQUENCY,
    )

    required_phase = normalize_text(
        phase
    )

    # ==============================================================
    # REQUIREMENT CALCULATION
    # ==============================================================

    requirement = calculate_inverter_requirement(
        running_load_w=running_load,
        surge_load_w=surge_load,
        continuous_margin=continuous_margin,
        surge_margin=surge_margin,
    )

    requirement[
        "dc_voltage"
    ] = nominal_system_voltage

    requirement[
        "system_voltage"
    ] = raw_system_voltage

    requirement[
        "output_voltage"
    ] = required_output_voltage

    requirement[
        "phase"
    ] = required_phase

    requirement[
        "frequency"
    ] = required_frequency

    # ==============================================================
    # DATABASE SELECTION
    # ==============================================================

    selection = select_inverter(
        inverter_requirement=requirement,
        inverters=inverters,
    )

    # ==============================================================
    # SUCCESS
    # ==============================================================

    if selection[
        "success"
    ]:

        selection[
            "required"
        ] = serialize_requirement(
            requirement
        )

        selection[
            "system_voltage"
        ] = output_number(
            raw_system_voltage
        )

        selection[
            "nominal_inverter_voltage"
        ] = output_number(
            nominal_system_voltage
        )

        return selection

    # ==============================================================
    # FAILURE
    # ==============================================================

    failure = dict(
        selection
    )

    # --------------------------------------------------------------
    # If no compatible inverter exists, identify the closest
    # available products.
    # --------------------------------------------------------------

    if (
        selection.get(
            "candidates"
        )
    ):

        # Reconstruct closest list from serialized candidates.
        closest = build_closest_from_serialized(
            selection[
                "candidates"
            ],
            limit=5,
        )

        failure[
            "closest"
        ] = closest

    failure[
        "required"
    ] = serialize_requirement(
        requirement
    )

    failure[
        "system_voltage"
    ] = output_number(
        raw_system_voltage
    )

    failure[
        "nominal_inverter_voltage"
    ] = output_number(
        nominal_system_voltage
    )

    failure.setdefault(
        "warnings",
        [],
    )

    # --------------------------------------------------------------
    # Specific user-facing explanation.
    # --------------------------------------------------------------

    if selection.get(
        "status"
    ) == "no_compatible_inverter":

        failure[
            "warnings"
        ].append(
            (
                "No inverter in the catalogue satisfies all "
                "required DC-voltage, continuous-power and "
                "surge-power requirements."
            )
        )

    failure[
        "messages"
    ] = messages

    return failure


# ==================================================================
# REQUIREMENT NORMALIZATION
# ==================================================================

def normalize_requirement(
    requirement: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Normalize the Phase 5 requirement dictionary.
    """

    return {
        "dc_voltage": normalize_system_voltage(
            requirement.get(
                "dc_voltage"
            )
        ),

        "system_voltage": positive(
            requirement.get(
                "system_voltage",
                requirement.get(
                    "dc_voltage"
                ),
            )
        ),

        "minimum_rated_power_w": positive(
            requirement.get(
                "minimum_rated_power_w",
                requirement.get(
                    "minimum_rated_power",
                    0,
                ),
            )
        ),

        "minimum_surge_power_w": positive(
            requirement.get(
                "minimum_surge_power_w",
                requirement.get(
                    "minimum_surge_power",
                    0,
                ),
            )
        ),

        "output_voltage": positive(
            requirement.get(
                "output_voltage",
                DEFAULT_OUTPUT_VOLTAGE,
            ),
            DEFAULT_OUTPUT_VOLTAGE,
        ),

        "phase": normalize_text(
            requirement.get(
                "phase"
            )
        ),

        "frequency": positive(
            requirement.get(
                "frequency",
                DEFAULT_FREQUENCY,
            ),
            DEFAULT_FREQUENCY,
        ),
    }


def validate_requirement(
    requirement: Dict[str, Any],
) -> List[str]:
    """
    Validate the engineering requirement.
    """

    errors = []

    if requirement[
        "dc_voltage"
    ] <= ZERO:

        errors.append(
            "A valid inverter DC/system voltage is required."
        )

    if requirement[
        "minimum_rated_power_w"
    ] <= ZERO:

        errors.append(
            "Minimum continuous inverter power must be greater than zero."
        )

    if requirement[
        "minimum_surge_power_w"
    ] <= ZERO:

        errors.append(
            "Minimum inverter surge power must be greater than zero."
        )

    if requirement[
        "minimum_surge_power_w"
    ] < requirement[
        "minimum_rated_power_w"
    ]:

        errors.append(
            "Minimum surge power cannot be lower than continuous power."
        )

    if requirement[
        "output_voltage"
    ] <= ZERO:

        errors.append(
            "Required AC output voltage must be greater than zero."
        )

    if requirement[
        "frequency"
    ] <= ZERO:

        errors.append(
            "Required AC frequency must be greater than zero."
        )

    return errors


def serialize_requirement(
    requirement: Dict[str, Any],
) -> Dict[str, Any]:
    """
    JSON-safe engineering requirement.
    """

    return {
        "dc_voltage": output_number(
            requirement.get(
                "dc_voltage",
                ZERO,
            )
        ),

        "system_voltage": output_number(
            requirement.get(
                "system_voltage",
                ZERO,
            )
        ),

        "minimum_rated_power_w": output_number(
            requirement.get(
                "minimum_rated_power_w",
                ZERO,
            )
        ),

        "minimum_rated_power_kw": output_number(
            to_decimal(
                requirement.get(
                    "minimum_rated_power_w",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "minimum_surge_power_w": output_number(
            requirement.get(
                "minimum_surge_power_w",
                ZERO,
            )
        ),

        "minimum_surge_power_kw": output_number(
            to_decimal(
                requirement.get(
                    "minimum_surge_power_w",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "running_load_w": output_number(
            requirement.get(
                "running_load_w",
                ZERO,
            )
        ),

        "running_load_kw": output_number(
            to_decimal(
                requirement.get(
                    "running_load_w",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "surge_load_w": output_number(
            requirement.get(
                "surge_load_w",
                ZERO,
            )
        ),

        "surge_load_kw": output_number(
            to_decimal(
                requirement.get(
                    "surge_load_w",
                    ZERO,
                )
            )
            /
            THOUSAND
        ),

        "continuous_margin": output_number(
            requirement.get(
                "continuous_margin",
                DEFAULT_CONTINUOUS_MARGIN,
            ),
            places=4,
        ),

        "surge_margin": output_number(
            requirement.get(
                "surge_margin",
                DEFAULT_SURGE_MARGIN,
            ),
            places=4,
        ),

        "output_voltage": output_number(
            requirement.get(
                "output_voltage",
                DEFAULT_OUTPUT_VOLTAGE,
            )
        ),

        "phase": requirement.get(
            "phase",
            "",
        ),

        "frequency": output_number(
            requirement.get(
                "frequency",
                DEFAULT_FREQUENCY,
            )
        ),
    }


# ==================================================================
# FAILURE CONTRACT
# ==================================================================

def failed_result(
    message: str,
    warnings: Optional[List[str]] = None,
    required: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Standard safe failure response.

    IMPORTANT:

    Every expected key is returned.

    Therefore callers can safely do:

        result.get("selected")

    without the entire calculator crashing.
    """

    return {
        "success": False,

        "status": "error",

        "required": (
            required
            if required is not None
            else {}
        ),

        "selected": None,

        "alternatives": [],

        "closest": [],

        "candidates": [],

        "warnings": (
            warnings
            if warnings
            else [message]
        ),

        "messages": [],

        "system_voltage": None,

        "nominal_inverter_voltage": None,

        "message": message,

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ==================================================================
# CLOSEST FROM SERIALIZED CANDIDATES
# ==================================================================

def build_closest_from_serialized(
    candidates: Iterable[Dict[str, Any]],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Produce a simple diagnostic closest-product list from already
    serialized candidate results.

    These products MUST NOT be treated as selected.
    """

    items = []

    for candidate in candidates:

        failures = candidate.get(
            "failures",
            []
        )

        checks = candidate.get(
            "checks",
            {}
        )

        voltage_penalty = (
            Decimal("1000000")
            if not checks.get(
                "dc_voltage",
                False,
            )
            else ZERO
        )

        power_gap = ZERO

        if not checks.get(
            "continuous_power",
            False,
        ):

            power_gap += max(
                ZERO,
                -to_decimal(
                    candidate.get(
                        "continuous_surplus_w",
                        ZERO,
                    )
                ),
            )

        surge_gap = ZERO

        if not checks.get(
            "surge_power",
            False,
        ):

            surge_gap += max(
                ZERO,
                -to_decimal(
                    candidate.get(
                        "surge_surplus_w",
                        ZERO,
                    )
                ),
            )

        score = (
            voltage_penalty
            +
            power_gap
            +
            surge_gap
            +
            Decimal(
                len(
                    failures
                )
            )
            *
            Decimal("1000")
        )

        items.append(
            (
                score,
                candidate,
            )
        )

    items.sort(
        key=lambda item: item[0]
    )

    return [
        item[1]
        for item in items[
            :limit
        ]
    ]


# ==================================================================
# PUBLIC ALIASES
# ==================================================================

run_inverter_engine = calculate_inverter

calculate_inverter_requirement = (
    calculate_inverter_requirement
)

select_best_inverter = select_inverter