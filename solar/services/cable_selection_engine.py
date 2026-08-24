# solar/services/cable_selection_engine.py

"""
Professional Solar PV Cable Database Selection Engine.

Responsibilities
----------------
1. Search the Cable database.
2. Enforce cable type compatibility.
3. Enforce minimum cross-sectional area.
4. Enforce minimum ampacity.
5. Enforce voltage rating.
6. Select the smallest suitable cable.
7. Return alternatives.
8. Return the closest available product when no fully compliant
   product exists.
9. Return JSON-safe dictionaries rather than Django model
   objects.

Engineering calculations belong in cable_engine.py.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from solar.models import CableSpecification


# ================================================================
# CONSTANTS
# ================================================================

ZERO = Decimal("0")


# ================================================================
# DECIMAL NORMALIZATION
# ================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert a value to Decimal.
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

    value = to_decimal(
        value,
        default,
    )

    return max(
        value,
        ZERO,
    )


# ================================================================
# CABLE SERIALIZATION
# ================================================================

def _serialize_cable(
    cable: CableSpecification,
    *,
    required_length: Decimal,
    required_size: Decimal,
    required_ampacity: Decimal,
    required_voltage_rating: Decimal,
    selection_reason: str,
) -> Dict[str, Any]:
    """
    Convert Cable model instance into a JSON-safe dictionary.

    Do not return the Django object itself because the result is
    eventually stored in SolarDesign.cable_result JSONField.
    """

    size_mm = to_decimal(
        cable.size_mm
    )

    ampacity = to_decimal(
        cable.ampacity
    )

    voltage_rating = (
        to_decimal(
            cable.voltage_rating
        )
        if cable.voltage_rating is not None
        else None
    )

    price_per_meter = to_decimal(
        cable.product.final_price
    )

    total_price = (
        price_per_meter
        * required_length
    )

    return {
        "id":
            cable.id,

        "manufacturer":
            cable.product.manufacturer or "",

        "name":
            cable.product.name,

        "cable":
            cable.product.name,

        "cable_type":
            cable.cable_type,

        "size_mm":
            size_mm,

        "size_mm2":
            size_mm,

        "ampacity":
            ampacity,

        "voltage_rating":
            voltage_rating,

        "price_per_meter":
            price_per_meter,

        "unit_price":
            price_per_meter,

        "length":
            required_length,

        "total_price":
            total_price,

        "total_cost":
            total_price,

        "required_size":
            required_size,

        "required_ampacity":
            required_ampacity,

        "required_voltage_rating":
            required_voltage_rating,

        "ampacity_margin":
            ampacity - required_ampacity,

        "size_margin":
            size_mm - required_size,

        "voltage_margin":
            (
                voltage_rating - required_voltage_rating
                if voltage_rating is not None
                else None
            ),

        "selection_reason":
            selection_reason,
    }


# ================================================================
# CLOSEST-CABLE SCORING
# ================================================================

def _calculate_gap_score(
    cable: CableSpecification,
    *,
    required_size: Decimal,
    required_ampacity: Decimal,
    required_voltage_rating: Decimal,
) -> Decimal:
    """
    Calculate a deterministic closeness score.

    A lower score means the cable is closer to satisfying the
    engineering requirement.

    The score is used ONLY when no fully compliant cable exists.
    """

    cable_size = to_decimal(
        cable.size_mm
    )

    cable_ampacity = to_decimal(
        cable.ampacity
    )

    cable_voltage = (
        to_decimal(
            cable.voltage_rating
        )
        if cable.voltage_rating is not None
        else ZERO
    )

    size_gap = max(
        required_size - cable_size,
        ZERO,
    )

    current_gap = max(
        required_ampacity - cable_ampacity,
        ZERO,
    )

    voltage_gap = max(
        required_voltage_rating - cable_voltage,
        ZERO,
    )

    # Weight current and voltage deficiencies more heavily than
    # a small size mismatch.
    score = (
        size_gap
        + (current_gap * Decimal("2"))
        + (voltage_gap / Decimal("100"))
    )

    return score


# ================================================================
# MAIN SELECTION ENGINE
# ================================================================

def select_cable(
    cable_requirement: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Select a suitable cable from the Cable database.

    Required engineering requirement fields:

        cable_type
        required_size
        required_current / required_ampacity
        required_voltage_rating
        length

    Selection logic:

        1. active cable
        2. correct cable type
        3. sufficient cross-sectional area
        4. sufficient ampacity
        5. sufficient voltage rating

    The smallest compliant cable is selected first.
    """

    warnings = []

    # ------------------------------------------------------------
    # VALIDATE INPUT
    # ------------------------------------------------------------

    if not cable_requirement:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "No cable engineering requirement was supplied.",
            "warnings": [
                "Run cable_engine before cable selection."
            ],
        }

    cable_type = str(
        cable_requirement.get(
            "cable_type",
            "",
        )
        or ""
    ).strip().lower()

    required_size = positive_decimal(
        cable_requirement.get(
            "required_size",
            0,
        )
    )

    required_ampacity = positive_decimal(
        cable_requirement.get(
            "required_ampacity",
            cable_requirement.get(
                "required_current",
                0,
            ),
        )
    )

    required_voltage_rating = positive_decimal(
        cable_requirement.get(
            "required_voltage_rating",
            cable_requirement.get(
                "system_voltage",
                0,
            ),
        )
    )

    required_length = positive_decimal(
        cable_requirement.get(
            "length",
            cable_requirement.get(
                "distance",
                0,
            ),
        )
    )

    if not cable_type:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "Cable type was not supplied.",
            "warnings": [
                "Cable type is required for database selection."
            ],
        }

    if required_size <= ZERO:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "Required cable size is invalid.",
            "warnings": [
                "Required cable cross-sectional area must be "
                "greater than zero."
            ],
        }

    if required_ampacity <= ZERO:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "Required cable ampacity is invalid.",
            "warnings": [
                "Required cable ampacity must be greater than zero."
            ],
        }

    if required_voltage_rating <= ZERO:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "Required cable voltage rating is invalid.",
            "warnings": [
                "Required cable voltage rating must be greater than zero."
            ],
        }

    # ------------------------------------------------------------
    # DATABASE QUERY
    # ------------------------------------------------------------

    available_cables = list(
        CableSpecification.objects
        .select_related("product")
    .filter(
        product__is_active=True,
        cable_type=cable_type,
    )
    .order_by(
        "size_mm",
        "ampacity",
        "voltage_rating",
        "product__cached_price",
    )
)

    if not available_cables:

        return {
            "success": False,
            "selected": None,
            "alternatives": [],
            "closest": None,
            "message":
                "No active cables of the required type exist "
                "in the database.",
            "warnings": [
                (
                    "Add active "
                    f"'{cable_type}' cable products to the Cable database."
                )
            ],
        }

    # ------------------------------------------------------------
    # FULLY COMPLIANT CABLES
    # ------------------------------------------------------------

    suitable = []

    for cable in available_cables:

        cable_size = to_decimal(
            cable.size_mm
        )

        cable_ampacity = to_decimal(
            cable.ampacity
        )

        cable_voltage = (
            to_decimal(
                cable.voltage_rating
            )
            if cable.voltage_rating is not None
            else ZERO
        )

        size_ok = (
            cable_size >= required_size
        )

        ampacity_ok = (
            cable_ampacity >= required_ampacity
        )

        voltage_ok = (
            cable_voltage >= required_voltage_rating
        )

        if (
            size_ok
            and ampacity_ok
            and voltage_ok
        ):
            suitable.append(
                cable
            )

    # ------------------------------------------------------------
    # SELECT BEST CABLE
    # ------------------------------------------------------------

    if suitable:

        # Primary criterion:
        # smallest compliant conductor.
        #
        # Secondary:
        # smallest excess ampacity.
        #
        # Tertiary:
        # lowest price.
        selected = min(
            suitable,
            key=lambda cable: (
                to_decimal(
                    cable.size_mm
                ),
                to_decimal(
                    cable.ampacity
                )
                -
                required_ampacity,
                to_decimal(
                    cable.product.final_price
                ),
            ),
        )

        selected_data = _serialize_cable(
            selected,
            required_length=required_length,
            required_size=required_size,
            required_ampacity=required_ampacity,
            required_voltage_rating=required_voltage_rating,
            selection_reason=(
                "Smallest active database cable satisfying "
                "size, ampacity and voltage-rating requirements."
            ),
        )

        # --------------------------------------------------------
        # ALTERNATIVES
        # --------------------------------------------------------

        alternatives = []

        for cable in suitable:

            if cable.id == selected.id:
                continue

            alternatives.append(
                _serialize_cable(
                    cable,
                    required_length=required_length,
                    required_size=required_size,
                    required_ampacity=required_ampacity,
                    required_voltage_rating=required_voltage_rating,
                    selection_reason=(
                        "Alternative compliant cable."
                    ),
                )
            )

        alternatives = sorted(
            alternatives,
            key=lambda item: (
                to_decimal(
                    item["size_mm"]
                ),
                to_decimal(
                    item["price_per_meter"]
                ),
            ),
        )

        return {
            "success": True,

            "selected":
                selected_data,

            "alternatives":
                alternatives,

            "closest":
                None,

            "message":
                "Suitable cable selected successfully.",

            "warnings":
                warnings,
        }

    # ------------------------------------------------------------
    # NO FULLY COMPLIANT CABLE
    # ------------------------------------------------------------

    closest = min(
        available_cables,
        key=lambda cable: _calculate_gap_score(
            cable,
            required_size=required_size,
            required_ampacity=required_ampacity,
            required_voltage_rating=required_voltage_rating,
        ),
    )

    closest_data = _serialize_cable(
        closest,
        required_length=required_length,
        required_size=required_size,
        required_ampacity=required_ampacity,
        required_voltage_rating=required_voltage_rating,
        selection_reason=(
            "Closest available database cable, but it does "
            "not satisfy all engineering requirements."
        ),
    )

    # ------------------------------------------------------------
    # CLOSEST-CABLE DIAGNOSTICS
    # ------------------------------------------------------------

    closest_size = to_decimal(
        closest.size_mm
    )

    closest_ampacity = to_decimal(
        closest.ampacity
    )

    closest_voltage = (
        to_decimal(
            closest.voltage_rating
        )
        if closest.voltage_rating is not None
        else ZERO
    )

    if closest_size < required_size:

        warnings.append(
            "Closest cable is undersized by cross-sectional area."
        )

    if closest_ampacity < required_ampacity:

        warnings.append(
            "Closest cable does not provide the required ampacity."
        )

    if closest_voltage < required_voltage_rating:

        warnings.append(
            "Closest cable does not have the required voltage rating."
        )

    warnings.append(
        "No cable in the database satisfies all engineering requirements."
    )

    warnings.append(
        "The closest available cable is shown for engineering review "
        "and must not be treated as automatically compliant."
    )

    return {
        "success": False,

        "selected":
            None,

        "alternatives":
            [],

        "closest":
            closest_data,

        "message":
            "No suitable cable found in the active database.",

        "warnings":
            list(dict.fromkeys(warnings)),
    }


# ================================================================
# MULTI-CIRCUIT SELECTION
# ================================================================

def select_cable_set(
    requirements: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Select multiple cable types in one operation.

    Example:

        {
            "pv": pv_requirement,
            "battery": battery_requirement,
            "ac": ac_requirement,
            "earth": earth_requirement,
        }
    """

    results = {}

    warnings = []

    all_successful = True

    for circuit_name, requirement in requirements.items():

        result = select_cable(
            cable_requirement=requirement
        )

        results[circuit_name] = result

        warnings.extend(
            result.get(
                "warnings",
                [],
            )
        )

        if not result.get(
            "success",
            False,
        ):
            all_successful = False

    return {
        "success":
            all_successful,

        "results":
            results,

        "warnings":
            list(dict.fromkeys(warnings)),

        "message": (
            "All cable types were selected successfully."
            if all_successful
            else
            "One or more cable types could not be selected "
            "from the active database."
        ),
    }