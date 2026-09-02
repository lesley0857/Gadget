"""
solar/services/controller_selection_engine.py

PHASE 6
CHARGE CONTROLLER / MPPT SELECTION ENGINE

Database-selection layer.

Engineering calculations are performed by:

    solar.services.controller_engine

This module selects actual ChargeController records from the
admin-managed catalogue.

A controller is considered electrically compatible only when it
satisfies all mandatory requirements.

Mandatory checks
----------------
1. Battery/system voltage
2. Maximum PV voltage
3. Maximum PV input/current capacity
4. Maximum battery charge current
5. Required controller power

The engine supports multiple identical controllers.

It never returns an undersized controller as "selected".

If no exact solution exists, the result contains:

    success = False
    selected = None
    closest = [...]

The closest controller is diagnostic information only.
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

from .controller_engine import calculate_controller_requirement
from .controller_engine import (
     HUNDRED, extract_system_voltage
)

# ==================================================================
# METADATA
# ==================================================================

ENGINE_NAME = "Charge Controller / MPPT Selection Engine"
ENGINE_VERSION = "6.0.0"


# ==================================================================
# CONSTANTS
# ==================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
THOUSAND = Decimal("1000")


# ==================================================================
# DECIMAL UTILITIES
# ==================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:

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

    number = to_decimal(
        value,
        default,
    )

    if number <= ZERO:
        return default

    return number


def normalize_nominal_voltage(
    value: Any,
) -> Decimal:
    """
    Normalize lithium nominal battery voltages:

        12.8 -> 12
        25.6 -> 24
        51.2 -> 48
    """

    voltage = positive(
        value
    )

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


def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:

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

    number = round_decimal(
        value,
        places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ==================================================================
# MODEL NORMALIZATION
# ==================================================================

def normalize_controller(
    controller: Any,
) -> Dict[str, Any]:
    """
    Convert a Django ChargeController instance or dictionary into
    the internal representation.
    """

    if isinstance(
        controller,
        dict,
    ):

        getter = controller.get

    else:

        getter = (
            lambda key, default=None:
            getattr(
                controller,
                key,
                default,
            )
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
        ).strip(),

        "model": str(
            getter(
                "model",
                "",
            )
            or ""
        ).strip(),

        "battery_voltage": to_decimal(
            getter(
                "battery_voltage",
                0,
            )
        ),

        "max_pv_voltage": to_decimal(
            getter(
                "max_pv_voltage",
                0,
            )
        ),

        "max_charge_current": to_decimal(
            getter(
                "max_charge_current",
                0,
            )
        ),

        "efficiency": to_decimal(
            getter(
                "efficiency",
                Decimal("0.98"),
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
# CONTROLLER VALIDATION
# ==================================================================

def validate_controller(
    controller: Dict[str, Any],
) -> List[str]:

    errors = []

    if controller[
        "battery_voltage"
    ] <= ZERO:

        errors.append(
            "Controller battery voltage is invalid."
        )

    if controller[
        "max_pv_voltage"
    ] <= ZERO:

        errors.append(
            "Controller maximum PV voltage is invalid."
        )

    if controller[
        "max_charge_current"
    ] <= ZERO:

        errors.append(
            "Controller maximum charge current is invalid."
        )

    if controller[
        "efficiency"
    ] <= ZERO:

        errors.append(
            "Controller efficiency is invalid."
        )

    return errors


# ==================================================================
# REQUIREMENT NORMALIZATION
# ==================================================================

def normalize_requirement(
    requirement: Dict[str, Any],
) -> Dict[str, Decimal]:

    return {
        "battery_voltage": normalize_nominal_voltage(
            requirement.get(
                "battery_voltage",
                0,
            )
        ),

        "minimum_pv_voltage": positive(
            requirement.get(
                "minimum_pv_voltage",
                0,
            )
        ),

        "minimum_pv_current": positive(
            requirement.get(
                "minimum_pv_current",
                0,
            )
        ),

        "minimum_charge_current": positive(
            requirement.get(
                "minimum_charge_current",
                0,
            )
        ),

        "minimum_pv_power": positive(
            requirement.get(
                "minimum_pv_power",
                0,
            )
        ),

        "minimum_controller_power": positive(
            requirement.get(
                "minimum_controller_power",
                0,
            )
        ),
    }


def validate_requirement(
    requirement: Dict[str, Decimal],
) -> List[str]:

    errors = []

    if requirement[
        "battery_voltage"
    ] <= ZERO:

        errors.append(
            "Battery/system voltage is required."
        )

    if requirement[
        "minimum_pv_voltage"
    ] <= ZERO:

        errors.append(
            "Minimum PV voltage is required."
        )

    if requirement[
        "minimum_pv_current"
    ] <= ZERO:

        errors.append(
            "Minimum PV current is required."
        )

    if requirement[
        "minimum_charge_current"
    ] <= ZERO:

        errors.append(
            "Minimum charge current is required."
        )

    if requirement[
        "minimum_pv_power"
    ] <= ZERO:

        errors.append(
            "Minimum PV power is required."
        )

    if requirement[
        "minimum_controller_power"
    ] <= ZERO:

        errors.append(
            "Minimum controller power is required."
        )

    return errors


# ==================================================================
# VOLTAGE COMPATIBILITY
# ==================================================================

def battery_voltage_compatible(
    controller_voltage: Any,
    required_voltage: Any,
) -> bool:

    controller = normalize_nominal_voltage(
        controller_voltage
    )

    required = normalize_nominal_voltage(
        required_voltage
    )

    if controller <= ZERO or required <= ZERO:
        return False

    return controller == required


# ==================================================================
# SINGLE CONTROLLER EVALUATION
# ==================================================================

def evaluate_controller(
    controller: Any,
    requirement: Dict[str, Decimal],
    quantity: int = 1,
) -> Dict[str, Any]:
    """
    Evaluate a single controller or a bank of identical controllers.

    Quantity is important because a large PV array may legitimately
    require multiple MPPT controllers.
    """

    record = normalize_controller(
        controller
    )

    validation_errors = validate_controller(
        record
    )

    quantity = max(
        1,
        int(
            quantity
        ),
    )

    # --------------------------------------------------------------
    # Aggregate controller capacity
    # --------------------------------------------------------------

    total_charge_current = (
        record[
            "max_charge_current"
        ]
        *
        quantity
    )

    total_controller_power = (
        total_charge_current
        *
        requirement[
            "battery_voltage"
        ]
    )

    # --------------------------------------------------------------
    # PV current is treated as an aggregate input requirement.
    #
    # A single-controller model does not contain an independent
    # maximum PV current field, so max_charge_current is used as the
    # available current capacity for the catalogue model.
    #
    # This is conservative and keeps the existing model contract.
    # --------------------------------------------------------------

    total_pv_current_capacity = (
        record[
            "max_charge_current"
        ]
        *
        quantity
    )

    # --------------------------------------------------------------
    # Checks
    # --------------------------------------------------------------

    checks = {
        "battery_voltage": battery_voltage_compatible(
            record[
                "battery_voltage"
            ],
            requirement[
                "battery_voltage"
            ],
        ),

        "pv_voltage": (
            record[
                "max_pv_voltage"
            ]
            >=
            requirement[
                "minimum_pv_voltage"
            ]
        ),

        "pv_current": (
            total_pv_current_capacity
            >=
            requirement[
                "minimum_pv_current"
            ]
        ),

        "charge_current": (
            total_charge_current
            >=
            requirement[
                "minimum_charge_current"
            ]
        ),

        "controller_power": (
            total_controller_power
            >=
            requirement[
                "minimum_controller_power"
            ]
        ),
    }

    compatible = (
        not validation_errors
        and
        all(
            checks.values()
        )
    )

    failures = list(
        validation_errors
    )

    if not checks[
        "battery_voltage"
    ]:

        failures.append(
            (
                "Battery voltage mismatch: "
                f"controller={output_number(record['battery_voltage'])} V, "
                f"required={output_number(requirement['battery_voltage'])} V."
            )
        )

    if not checks[
        "pv_voltage"
    ]:

        failures.append(
            (
                "Insufficient PV voltage rating: "
                f"controller={output_number(record['max_pv_voltage'])} V, "
                f"required={output_number(requirement['minimum_pv_voltage'])} V."
            )
        )

    if not checks[
        "pv_current"
    ]:

        failures.append(
            (
                "Insufficient PV current capacity: "
                f"controller bank={output_number(total_pv_current_capacity)} A, "
                f"required={output_number(requirement['minimum_pv_current'])} A."
            )
        )

    if not checks[
        "charge_current"
    ]:

        failures.append(
            (
                "Insufficient charging-current capacity: "
                f"controller bank={output_number(total_charge_current)} A, "
                f"required={output_number(requirement['minimum_charge_current'])} A."
            )
        )

    if not checks[
        "controller_power"
    ]:

        failures.append(
            (
                "Insufficient controller power capacity: "
                f"controller bank={output_number(total_controller_power)} W, "
                f"required={output_number(requirement['minimum_controller_power'])} W."
            )
        )

    # --------------------------------------------------------------
    # Utilization
    # --------------------------------------------------------------

    charge_utilization = (
        requirement[
            "minimum_charge_current"
        ]
        /
        total_charge_current
        if total_charge_current > ZERO
        else Decimal("999")
    )

    power_utilization = (
        requirement[
            "minimum_controller_power"
        ]
        /
        total_controller_power
        if total_controller_power > ZERO
        else Decimal("999")
    )

    pv_current_utilization = (
        requirement[
            "minimum_pv_current"
        ]
        /
        total_pv_current_capacity
        if total_pv_current_capacity > ZERO
        else Decimal("999")
    )

    # --------------------------------------------------------------
    # Capacity surplus
    # --------------------------------------------------------------

    charge_surplus = (
        total_charge_current
        -
        requirement[
            "minimum_charge_current"
        ]
    )

    power_surplus = (
        total_controller_power
        -
        requirement[
            "minimum_controller_power"
        ]
    )

    pv_current_surplus = (
        total_pv_current_capacity
        -
        requirement[
            "minimum_pv_current"
        ]
    )

    # --------------------------------------------------------------
    # Score
    # --------------------------------------------------------------

    score = calculate_score(
        record=record,
        requirement=requirement,
        quantity=quantity,
        charge_utilization=charge_utilization,
        power_utilization=power_utilization,
        pv_current_utilization=pv_current_utilization,
    )

    return {
        "compatible": compatible,

        "controller": record,

        "quantity": quantity,

        "checks": checks,

        "failures": failures,

        "total_charge_current": (
            total_charge_current
        ),

        "total_controller_power": (
            total_controller_power
        ),

        "total_pv_current_capacity": (
            total_pv_current_capacity
        ),

        "charge_surplus": charge_surplus,

        "power_surplus": power_surplus,

        "pv_current_surplus": pv_current_surplus,

        "charge_utilization": (
            charge_utilization
        ),

        "power_utilization": (
            power_utilization
        ),

        "pv_current_utilization": (
            pv_current_utilization
        ),

        "score": score,
    }


# ==================================================================
# SCORING
# ==================================================================

def calculate_score(
    record: Dict[str, Any],
    requirement: Dict[str, Decimal],
    quantity: int,
    charge_utilization: Decimal,
    power_utilization: Decimal,
    pv_current_utilization: Decimal,
) -> Decimal:
    """
    Rank electrically compatible configurations.

    Preference:

        1. smallest practical quantity
        2. reasonable controller utilization
        3. adequate but not excessive PV voltage capacity
        4. adequate current capacity
        5. higher efficiency
        6. lower price
    """

    score = Decimal("100")

    # --------------------------------------------------------------
    # Controller quantity
    # --------------------------------------------------------------

    score -= (
        Decimal(
            quantity - 1
        )
        *
        Decimal("12")
    )

    # --------------------------------------------------------------
    # Charge utilization
    # --------------------------------------------------------------

    if (
        Decimal("0.50")
        <=
        charge_utilization
        <=
        Decimal("0.85")
    ):

        score += Decimal("18")

    elif (
        Decimal("0.85")
        <
        charge_utilization
        <=
        Decimal("0.95")
    ):

        score += Decimal("8")

    elif charge_utilization > Decimal("0.95"):

        score -= Decimal("10")

    elif charge_utilization < Decimal("0.30"):

        score -= Decimal("8")

    # --------------------------------------------------------------
    # Power utilization
    # --------------------------------------------------------------

    if (
        Decimal("0.50")
        <=
        power_utilization
        <=
        Decimal("0.90")
    ):

        score += Decimal("10")

    elif power_utilization > Decimal("0.95"):

        score -= Decimal("8")

    # --------------------------------------------------------------
    # PV current utilization
    # --------------------------------------------------------------

    if (
        Decimal("0.50")
        <=
        pv_current_utilization
        <=
        Decimal("0.90")
    ):

        score += Decimal("8")

    elif pv_current_utilization > Decimal("0.95"):

        score -= Decimal("8")

    # --------------------------------------------------------------
    # Efficiency
    # --------------------------------------------------------------

    efficiency = record[
        "efficiency"
    ]

    # Support both:
    #
    # 0.98
    # 98
    #

    if efficiency > ONE:

        efficiency /= HUNDRED

    if efficiency >= Decimal("0.98"):

        score += Decimal("12")

    elif efficiency >= Decimal("0.96"):

        score += Decimal("9")

    elif efficiency >= Decimal("0.94"):

        score += Decimal("5")

    elif efficiency >= Decimal("0.90"):

        score += Decimal("2")

    else:

        score -= Decimal("5")

    # --------------------------------------------------------------
    # Price
    # --------------------------------------------------------------

    if record[
        "price"
    ] > ZERO:

        # Cost should influence ranking but never override
        # electrical suitability.
        score -= min(
            Decimal("10"),
            record[
                "price"
            ]
            /
            Decimal("1000000")
            *
            Decimal("10"),
        )

    return max(
        ZERO,
        score,
    )


# ==================================================================
# SERIALIZATION
# ==================================================================

def serialize_controller(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert controller result to JSON-safe values.
    """

    record = result.get(
        "controller",
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

        "quantity": int(
            result.get(
                "quantity",
                1,
            )
        ),

        "battery_voltage": output_number(
            record.get(
                "battery_voltage",
                ZERO,
            )
        ),

        "max_pv_voltage": output_number(
            record.get(
                "max_pv_voltage",
                ZERO,
            )
        ),

        "max_charge_current": output_number(
            record.get(
                "max_charge_current",
                ZERO,
            )
        ),

        "efficiency": output_number(
            record.get(
                "efficiency",
                ZERO,
            ),
            places=4,
        ),

        "unit_price": output_number(
            record.get(
                "price",
                ZERO,
            )
        ),

        "total_price": output_number(
            record.get(
                "price",
                ZERO,
            )
            *
            result.get(
                "quantity",
                1,
            )
        ),

        "total_charge_current": output_number(
            result.get(
                "total_charge_current",
                ZERO,
            )
        ),

        "total_controller_power": output_number(
            result.get(
                "total_controller_power",
                ZERO,
            )
        ),

        "total_pv_current_capacity": output_number(
            result.get(
                "total_pv_current_capacity",
                ZERO,
            )
        ),

        "charge_surplus": output_number(
            result.get(
                "charge_surplus",
                ZERO,
            )
        ),

        "power_surplus": output_number(
            result.get(
                "power_surplus",
                ZERO,
            )
        ),

        "pv_current_surplus": output_number(
            result.get(
                "pv_current_surplus",
                ZERO,
            )
        ),

        "charge_utilization": output_number(
            result.get(
                "charge_utilization",
                ZERO,
            ),
            places=4,
        ),

        "power_utilization": output_number(
            result.get(
                "power_utilization",
                ZERO,
            ),
            places=4,
        ),

        "pv_current_utilization": output_number(
            result.get(
                "pv_current_utilization",
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


# ==================================================================
# MAIN SELECTION ENGINE
# ==================================================================

def select_charge_controller(
    controller_requirement: Optional[Dict[str, Any]],
    controllers: Optional[Iterable[Any]] = None,
    max_quantity: int = 12,
) -> Dict[str, Any]:
    """
    Select the best actual ChargeController configuration.

    The engine evaluates quantities:

        1 × controller
        2 × controller
        3 × controller
        ...

    until a valid configuration is found.

    This is necessary because a single 100 A controller should not
    be considered the only possible architecture for a 250 A charging
    requirement.

    However, each controller must individually be capable of handling
    the PV voltage requirement.
    """

    if not controller_requirement:

        return failure_result(
            message=(
                "No controller engineering requirement was supplied."
            ),
            warnings=[
                (
                    "Run calculate_controller_requirement() "
                    "before selecting a controller."
                )
            ],
        )

    requirement = normalize_requirement(
        controller_requirement
    )

    errors = validate_requirement(
        requirement
    )

    if errors:

        return failure_result(
            message=(
                "The charge-controller requirement is invalid."
            ),
            warnings=errors,
            requirement=serialize_requirement(
                requirement
            ),
        )

    # ==============================================================
    # LOAD DATABASE
    # ==============================================================

    if controllers is None:

        try:

            from solar.services import product_bridge
            controllers = product_bridge.get_active_controllers()

        except Exception as exc:

            return failure_result(
                message=(
                    "The charge-controller catalogue could not "
                    "be loaded."
                ),
                warnings=[
                    (
                        "The Solar ChargeController model could "
                        "not be accessed."
                    ),
                    str(exc),
                ],
                requirement=serialize_requirement(
                    requirement
                ),
            )

    # ==============================================================
    # EVALUATION
    # ==============================================================

    evaluated = []

    try:

        controller_list = list(
            controllers
        )

    except Exception as exc:

        return failure_result(
            message=(
                "The charge-controller catalogue could not be read."
            ),
            warnings=[
                str(exc)
            ],
            requirement=serialize_requirement(
                requirement
            ),
        )

    if not controller_list:

        return failure_result(
            message=(
                "No active charge controllers are available."
            ),
            warnings=[
                (
                    "Add active MPPT charge controllers to the "
                    "admin catalogue before running the calculator."
                )
            ],
            requirement=serialize_requirement(
                requirement
            ),
        )

    # ==============================================================
    # EVALUATE QUANTITIES
    # ==============================================================

    for controller in controller_list:

        record = normalize_controller(
            controller
        )

        if not record[
            "active"
        ]:

            continue

        # ----------------------------------------------------------
        # A controller's own PV voltage limit cannot be combined
        # across multiple controllers. Every controller receiving
        # the same PV configuration must be voltage compatible.
        # ----------------------------------------------------------

        if record[
            "max_pv_voltage"
        ] < requirement[
            "minimum_pv_voltage"
        ]:

            # Still evaluate quantity 1 for diagnostic purposes.
            result = evaluate_controller(
                controller=record,
                requirement=requirement,
                quantity=1,
            )

            evaluated.append(
                result
            )

            continue

        # ----------------------------------------------------------
        # Determine minimum quantity required from charge current.
        # ----------------------------------------------------------

        if record[
            "max_charge_current"
        ] > ZERO:

            required_quantity = int(
                (
                    requirement[
                        "minimum_charge_current"
                    ]
                    /
                    record[
                        "max_charge_current"
                    ]
                ).to_integral_value(
                    rounding="ROUND_CEILING"
                )
            )

        else:

            required_quantity = max_quantity + 1

        required_quantity = max(
            1,
            required_quantity,
        )

        # Evaluate a reasonable range around the minimum.
        #
        # This allows the scoring engine to choose between:
        #
        # 2 × 100 A
        # 3 × 100 A
        #
        # when both satisfy the requirement.
        #
        start_quantity = max(
            1,
            required_quantity,
        )

        end_quantity = min(
            max_quantity,
            start_quantity + 3,
        )

        for quantity in range(
            start_quantity,
            end_quantity + 1,
        ):

            result = evaluate_controller(
                controller=record,
                requirement=requirement,
                quantity=quantity,
            )

            evaluated.append(
                result
            )

    # ==============================================================
    # COMPATIBLE CONFIGURATIONS
    # ==============================================================

    compatible = [
        result
        for result in evaluated
        if result.get(
            "compatible",
            False,
        )
    ]

    if compatible:

        compatible.sort(
            key=lambda result: (
                -result.get(
                    "score",
                    ZERO,
                ),

                result.get(
                    "quantity",
                    999,
                ),

                result.get(
                    "total_charge_current",
                    ZERO,
                ),

                result.get(
                    "controller",
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

        # ----------------------------------------------------------
        # High utilization warning
        # ----------------------------------------------------------

        if (
            selected[
                "charge_utilization"
            ]
            >
            Decimal("0.90")
        ):

            warnings.append(
                (
                    "The selected controller configuration is "
                    "operating above 90% of its charge-current capacity."
                )
            )

        # ----------------------------------------------------------
        # Multiple controller warning
        # ----------------------------------------------------------

        if selected[
            "quantity"
        ] > 1:

            warnings.append(
                (
                    f"{selected['quantity']} identical MPPT "
                    "controllers are required to satisfy the "
                    "calculated charging-current requirement."
                )
            )

        # ----------------------------------------------------------
        # PV power warning
        # ----------------------------------------------------------

        if requirement[
            "minimum_pv_power"
        ] > selected[
            "total_controller_power"
        ]:

            warnings.append(
                (
                    "The PV array power exceeds the aggregate "
                    "nominal controller charging-power capacity. "
                    "Verify the manufacturer's permitted PV "
                    "oversizing ratio before final approval."
                )
            )

        selected_serialized = serialize_controller(
            selected
        )

        return {
            "success": True,

            "status": "selected",

            "requirement": serialize_requirement(
                requirement
            ),

            "selected": selected_serialized,

            "alternatives": [
                serialize_controller(
                    result
                )
                for result in alternatives
            ],

            "closest": [],

            "candidates": [
                serialize_controller(
                    result
                )
                for result in compatible
            ],

            "warnings": warnings,

            "messages": [
                (
                    f"{selected_serialized['name']} "
                    f"({selected_serialized['quantity']} unit"
                    f"{'s' if selected_serialized['quantity'] != 1 else ''}) "
                    "satisfies the MPPT engineering requirements."
                )
            ],

            "message": (
                f"{selected_serialized['name']} "
                f"({selected_serialized['quantity']} unit"
                f"{'s' if selected_serialized['quantity'] != 1 else ''}) "
                "is the recommended charge-controller configuration."
            ),

            "engine": ENGINE_NAME,

            "engine_version": ENGINE_VERSION,
        }

    # ==============================================================
    # NO COMPATIBLE CONFIGURATION
    # ==============================================================

    closest = find_closest_configurations(
        evaluated,
        requirement,
        limit=5,
    )

    warnings = [
        (
            "No charge-controller configuration in the active "
            "catalogue satisfies all mandatory MPPT requirements."
        ),
        (
            "The closest configurations shown are diagnostic "
            "suggestions only and must not be treated as selected "
            "equipment."
        ),
    ]

    return {
        "success": False,

        "status": "no_compatible_controller",

        "requirement": serialize_requirement(
            requirement
        ),

        "selected": None,

        "alternatives": [],

        "closest": closest,

        "candidates": [
            serialize_controller(
                result
            )
            for result in evaluated
        ],

        "warnings": warnings,

        "messages": [],

        "message": (
            "No suitable charge controller configuration was found."
        ),

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ==================================================================
# CLOSEST CONFIGURATION
# ==================================================================

def find_closest_configurations(
    evaluated: Iterable[Dict[str, Any]],
    requirement: Dict[str, Decimal],
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Return the closest controller configurations.

    These are NOT compatible selections.
    """

    scored = []

    for result in evaluated:

        controller = result.get(
            "controller",
            {},
        )

        checks = result.get(
            "checks",
            {},
        )

        failures = result.get(
            "failures",
            [],
        )

        # ----------------------------------------------------------
        # Voltage mismatch is heavily penalized.
        # ----------------------------------------------------------

        voltage_gap = max(
            ZERO,
            requirement[
                "minimum_pv_voltage"
            ]
            -
            controller.get(
                "max_pv_voltage",
                ZERO,
            ),
        )

        if not checks.get(
            "battery_voltage",
            False,
        ):

            battery_voltage_gap = (
                abs(
                    normalize_nominal_voltage(
                        controller.get(
                            "battery_voltage",
                            ZERO,
                        )
                    )
                    -
                    requirement[
                        "battery_voltage"
                    ]
                )
                *
                Decimal("100")
            )

        else:

            battery_voltage_gap = ZERO

        current_gap = max(
            ZERO,
            requirement[
                "minimum_charge_current"
            ]
            -
            result.get(
                "total_charge_current",
                ZERO,
            ),
        )

        power_gap = max(
            ZERO,
            requirement[
                "minimum_controller_power"
            ]
            -
            result.get(
                "total_controller_power",
                ZERO,
            ),
        )

        distance_score = (
            voltage_gap
            *
            Decimal("1000")
            +
            battery_voltage_gap
            *
            Decimal("10000")
            +
            current_gap
            *
            Decimal("10")
            +
            power_gap
            /
            Decimal("100")
            +
            Decimal(
                len(
                    failures
                )
            )
            *
            Decimal("100")
        )

        scored.append(
            (
                distance_score,
                result,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].get(
                "quantity",
                999,
            ),
        )
    )

    return [
        serialize_controller(
            result
        )
        for _, result in scored[
            :limit
        ]
    ]


# ==================================================================
# REQUIREMENT SERIALIZATION
# ==================================================================

def serialize_requirement(
    requirement: Dict[str, Decimal],
) -> Dict[str, Any]:

    return {
        "battery_voltage": output_number(
            requirement.get(
                "battery_voltage",
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
    }


# ==================================================================
# FAILURE RESULT
# ==================================================================

def failure_result(
    message: str,
    warnings: Optional[List[str]] = None,
    requirement: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return {
        "success": False,

        "status": "error",

        "requirement": (
            requirement
            if requirement is not None
            else {}
        ),

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
# COMPLETE PHASE 6 PUBLIC FUNCTION
# ==================================================================

def calculate_charge_controller(
    system_voltage: Any,
    panel_result: Optional[Dict[str, Any]],
    voltage_result: Optional[Dict[str, Any]] = None,
    battery_result: Optional[Dict[str, Any]] = None,
    controllers: Optional[Iterable[Any]] = None,
    safety_factor: Any = Decimal("1.25"),
    pv_voltage_margin: Any = Decimal("1.05"),
    pv_current_margin: Any = Decimal("1.25"),
    charge_current_margin: Any = Decimal("1.25"),
) -> Dict[str, Any]:
    """
    Complete Phase 6 entry point.

    Pipeline:

        Phase 2 / Phase 3
                ↓
        system voltage
                ↓
        Phase 4 PV array
                ↓
        engineering requirement
                ↓
        controller catalogue
                ↓
        controller configuration
    """

    # ==============================================================
    # ENGINEERING
    # ==============================================================

    requirement_result = (
        _calculate_requirement_with_sources(
            system_voltage=system_voltage,
            panel_result=panel_result,
            voltage_result=voltage_result,
            battery_result=battery_result,
            safety_factor=safety_factor,
            pv_voltage_margin=pv_voltage_margin,
            pv_current_margin=pv_current_margin,
            charge_current_margin=charge_current_margin,
        )
    )

    if not requirement_result.get(
        "success",
        False,
    ):

        return requirement_result

    # ==============================================================
    # SELECTION
    # ==============================================================

    selection_result = select_charge_controller(
        controller_requirement=(
            requirement_result[
                "requirement"
            ]
        ),
        controllers=controllers,
    )

    # ==============================================================
    # COMBINE ENGINE + SELECTION
    # ==============================================================
    
    result = dict(
        selection_result
    )

    result[
        "engineering"
    ] = requirement_result

    result[
        "design"
    ] = requirement_result.get(
        "design",
        {},
    )

    # Keep requirement at the top level because your existing
    # template architecture already expects:
    #
    # controller_result.requirement
    #
    result[
        "requirement"
    ] = requirement_result.get(
        "requirement",
        {},
    )

    # --------------------------------------------------------------
    # Merge engineering warnings.
    # --------------------------------------------------------------

    engineering_warnings = (
        requirement_result.get(
            "warnings",
            [],
        )
    )

    selection_warnings = (
        result.get(
            "warnings",
            [],
        )
    )

    result[
        "warnings"
    ] = list(
        dict.fromkeys(
            engineering_warnings
            +
            selection_warnings
        )
    )

    result[
        "engine"
    ] = ENGINE_NAME

    result[
        "engine_version"
    ] = ENGINE_VERSION

    return result


def _calculate_requirement_with_sources(
    system_voltage: Any,
    panel_result: Optional[Dict[str, Any]],
    voltage_result: Optional[Dict[str, Any]],
    battery_result: Optional[Dict[str, Any]],
    safety_factor: Any,
    pv_voltage_margin: Any,
    pv_current_margin: Any,
    charge_current_margin: Any,
) -> Dict[str, Any]:
    """
    Internal wrapper that resolves the canonical system voltage
    before performing engineering calculations.
    """
    
    resolved_voltage = extract_system_voltage(
        system_voltage=system_voltage,
        voltage_result=voltage_result,
        battery_result=battery_result,
    )

    return calculate_controller_requirement(
        system_voltage=resolved_voltage,
        panel_result=panel_result,
        safety_factor=safety_factor,
        pv_voltage_margin=pv_voltage_margin,
        pv_current_margin=pv_current_margin,
        charge_current_margin=charge_current_margin,
    )


# ==================================================================
# PUBLIC COMPATIBILITY ALIASES
# ==================================================================

run_controller_selection = select_charge_controller

select_best_controller = select_charge_controller