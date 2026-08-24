"""
solar/services/accessories_engine.py

PHASE 9
ACCESSORIES ENGINE

Responsibilities
----------------
This engine determines the non-primary accessories required to
assemble and install the solar PV system.

It consumes engineering results from the preceding phases:

    Phase 1  -> Load Engine
    Phase 2  -> System Voltage Engine
    Phase 3  -> Battery Engine / Battery Selection
    Phase 4  -> PV Panel Engine / Panel Selection
    Phase 5  -> Inverter Engine / Inverter Selection
    Phase 6  -> Charge Controller Engine / Selection
    Phase 7  -> Cable Engine / Cable Selection
    Phase 8  -> Protection Engine

It produces the accessory requirement used by:

    Phase 10 -> BOQ Engine
    Phase 11 -> Pricing Engine

IMPORTANT
---------
This engine does NOT:

    - select batteries
    - select panels
    - select inverters
    - select charge controllers
    - size cables
    - size protection
    - select protection devices
    - calculate system voltage
    - calculate PV array size
    - calculate battery capacity

Those responsibilities belong to the preceding engines.

The Accessories Engine only determines the supporting materials
required to physically assemble and install the already-designed
system.

DATABASE
--------
Accessory products are read from:

    solar.models.Accessory

The engine never assumes that a particular accessory exists in
the database.

If an engineering requirement exists but the corresponding
catalogue item is unavailable, the requirement is still returned
and a warning is generated.

This is intentional.

The engineering design must never disappear merely because an
accessory has not yet been entered into the admin catalogue.

NUMERIC POLICY
--------------
All engineering quantities and monetary calculations use Decimal.

No engineering calculation uses binary floating-point arithmetic.

OUTPUT
------
The canonical result has the following structure:

{
    "success": True,

    "required": {...},

    "items": [...],

    "categories": {
        "pv": [...],
        "battery": [...],
        "inverter": [...],
        "controller": [...],
        "cabling": [...],
        "mounting": [...],
        "earthing": [...],
        "general": [...]
    },

    "summary": {...},

    "warnings": [...],

    "messages": [...],

    "engine": "...",

    "engine_version": "..."
}
"""

from __future__ import annotations

from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_CEILING,
    ROUND_HALF_UP,
)
from typing import Any, Dict, Iterable, List, Optional

from django.db.models import QuerySet

from ..models import AccessorySpecification


# ==================================================================
# ENGINE METADATA
# ==================================================================

ENGINE_NAME = "Solar Accessories Engineering Engine"
ENGINE_VERSION = "9.0.0"


# ==================================================================
# DECIMAL CONSTANTS
# ==================================================================

ZERO = Decimal("0")
ONE = Decimal("1")
TWO = Decimal("2")
FOUR = Decimal("4")
EIGHT = Decimal("8")
TEN = Decimal("10")
HUNDRED = Decimal("100")


# ==================================================================
# DEFAULT ENGINEERING RULES
# ==================================================================

"""
These are installation-estimation rules.

They are deliberately centralized so that they can later be moved
to DesignSetting or another configuration model without rewriting
the engine.
"""

# --------------------------------------------------------------
# PV mounting hardware
# --------------------------------------------------------------

# Minimum clamp quantity per module.
DEFAULT_CLAMPS_PER_PANEL = Decimal("4")

# General mounting fasteners per module.
DEFAULT_BOLTS_PER_PANEL = Decimal("4")
DEFAULT_NUTS_PER_PANEL = Decimal("4")
DEFAULT_WASHERS_PER_PANEL = Decimal("4")


# --------------------------------------------------------------
# PV connector estimation
# --------------------------------------------------------------

# Minimum connector pairs for a PV installation.
MINIMUM_MC4_PAIRS = Decimal("2")

# Connector pairs estimated per parallel PV string.
MC4_PAIRS_PER_STRING = Decimal("2")


# --------------------------------------------------------------
# Cable accessories
# --------------------------------------------------------------

# Minimum cable glands for a small installation.
MINIMUM_CABLE_GLANDS = Decimal("4")

# Additional gland allowance for every 10 m of combined cable route.
CABLE_GLANDS_PER_10M = Decimal("1")


# --------------------------------------------------------------
# Battery accessories
# --------------------------------------------------------------

# Minimum cable lugs for a battery installation.
MINIMUM_BATTERY_LUGS = Decimal("8")

# Two terminals per battery is a conservative procurement allowance
# when the exact battery interconnection topology is not available.
LUGS_PER_BATTERY = Decimal("2")


# --------------------------------------------------------------
# Battery racks
# --------------------------------------------------------------

# Default batteries accommodated by one rack.
BATTERIES_PER_RACK = Decimal("4")


# --------------------------------------------------------------
# Earthing accessories
# --------------------------------------------------------------

# Minimum earthing accessory allowance where the cable/protection
# design indicates an earthing system is present.
MINIMUM_EARTHING_ITEMS = Decimal("1")


# ==================================================================
# ACCESSORY CATEGORY MAP
# ==================================================================

ACCESSORY_CATEGORY_MAP = {
    "clamp": "mounting",
    "bolt": "mounting",
    "nut": "mounting",
    "washer": "mounting",
    "hanger": "mounting",
    "rail": "mounting",
    "battery_rack": "battery",
    "lug": "cabling",
    "gland": "cabling",
    "connector": "pv",
    "trunking": "cabling",
    "conduit": "cabling",
    "earthing": "earthing",
    "other": "general",
}


# ==================================================================
# SAFE DECIMAL CONVERSION
# ==================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert a value safely to Decimal.

    Floats are converted through str() to avoid binary floating
    point artefacts.
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


# ==================================================================
# POSITIVE / NON-NEGATIVE HELPERS
# ==================================================================

def non_negative(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Convert to Decimal and clamp negative values to zero.
    """

    number = to_decimal(
        value,
        default=default,
    )

    if number < ZERO:
        return ZERO

    return number


def positive(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Return a positive Decimal.

    Zero and negative values become the supplied default.
    """

    number = to_decimal(
        value,
        default=default,
    )

    if number <= ZERO:
        return default

    return number


# ==================================================================
# INTEGER QUANTITY
# ==================================================================

def quantity_ceiling(
    value: Any,
) -> int:
    """
    Convert a quantity to the smallest whole number capable of
    satisfying the supplied requirement.
    """

    number = non_negative(value)

    return int(
        number.to_integral_value(
            rounding=ROUND_CEILING,
        )
    )


def safe_quantity(
    value: Any,
    minimum: int = 0,
) -> int:
    """
    Normalize an integer quantity.
    """

    quantity = quantity_ceiling(value)

    if quantity < minimum:
        return minimum

    return quantity


# ==================================================================
# ROUNDING
# ==================================================================

def round_decimal(
    value: Any,
    places: int = 2,
) -> Decimal:
    """
    Engineering rounding helper.
    """

    number = to_decimal(value)

    quantum = Decimal("1").scaleb(-places)

    return number.quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )


# ==================================================================
# JSON / TEMPLATE SAFE NUMBER
# ==================================================================

def number(
    value: Any,
    places: int = 2,
):
    """
    Convert Decimal to a template/JSON friendly number.
    """

    rounded = round_decimal(
        value,
        places=places,
    )

    if rounded == rounded.to_integral_value():
        return int(rounded)

    return float(rounded)


# ==================================================================
# GENERIC RESULT ACCESS
# ==================================================================

def _mapping_value(
    data: Any,
    *keys: str,
    default: Any = None,
):
    """
    Safely retrieve a value from a dictionary.

    This deliberately supports multiple known result locations
    used by the preceding engineering engines.

    It does not assume that every previous engine has exactly the
    same nesting depth.
    """

    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data:
            value = data.get(key)

            if value is not None:
                return value

    return default


def _nested_value(
    data: Any,
    paths: Iterable[Iterable[str]],
    default: Any = None,
):
    """
    Try multiple nested dictionary paths.
    """

    for path in paths:

        current = data

        valid = True

        for key in path:

            if not isinstance(current, dict):
                valid = False
                break

            if key not in current:
                valid = False
                break

            current = current[key]

        if valid and current is not None:
            return current

    return default


# ==================================================================
# SELECTED / REQUIRED DATA EXTRACTION
# ==================================================================

def _selected_or_required(
    result: Any,
) -> Dict[str, Any]:
    """
    Return the selected product data when available.

    Otherwise return engineering requirement data.

    This is important because the Accessories Engine must still
    operate when a required product is not currently available
    in the catalogue.
    """

    if not isinstance(result, dict):
        return {}

    selected = result.get("selected")

    if isinstance(selected, dict) and selected:
        return selected

    required = result.get("required")

    if isinstance(required, dict):
        return required

    return {}


# ==================================================================
# ACCESSORY CATALOGUE LOOKUP
# ==================================================================

def get_accessories_by_type(
    accessory_type: str,
):
    return (
        AccessorySpecification.objects
        .select_related("product")
        .filter(
            product__is_active=True,
            accessory_type=accessory_type,
        )
        .order_by(
            "product__cached_price",
            "id",
        )
    )


def get_accessory(
    accessory_type: str,
) -> Optional[AccessorySpecification]:
    """
    Return the lowest-priced active accessory of the requested type.

    Product selection remains catalogue-based only.

    The engineering quantity is calculated independently.
    """

    return (
        get_accessories_by_type(
            accessory_type
        )
        .first()
    )


# ==================================================================
# ACCESSORY ITEM CREATION
# ==================================================================

def _create_item(
    *,
    accessory: Optional[AccessorySpecification],
    accessory_type: str,
    quantity: int,
    category: str,
    requirement_source: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a standardized accessory result item.

    No Django model object is included in the returned dictionary.

    This makes the result safe for:

        - JSONField
        - request.session
        - API responses
        - templates
        - BOQ engine
        - pricing engine
    """

    quantity = safe_quantity(
        quantity
    )

    if accessory is not None:

        unit = (
            getattr(
                accessory,
                "unit",
                None,
            )
            or "pcs"
        )

        unit_price = to_decimal(
            accessory.product.final_price()
        )

        name = str(
            accessory.product.name or ""
        )

        accessory_id = accessory.product_id

        description_value = (
            description
            or accessory.product.description
            or name
        )

        availability = "available"

    else:

        unit = "pcs"

        unit_price = ZERO

        name = (
            description
            or accessory_type.replace(
                "_",
                " ",
            ).title()
        )

        accessory_id = None

        description_value = (
            description
            or name
        )

        availability = "not_in_catalogue"

    total_price = (
        unit_price
        * Decimal(quantity)
    )

    return {
        "accessory_id": accessory_id,

        "name": name,

        "type": accessory_type,

        "category": category,

        "description": description_value,

        "quantity": quantity,

        "unit": str(unit),

        "unit_price": round_decimal(
            unit_price
        ),

        "total_price": round_decimal(
            total_price
        ),

        "availability": availability,

        "requirement_source": (
            requirement_source
        ),
    }


# ==================================================================
# ADD ITEM
# ==================================================================

def _add_item(
    items: List[Dict[str, Any]],
    warnings: List[str],
    messages: List[str],
    *,
    accessory_type: str,
    quantity: int,
    category: str,
    requirement_source: str,
    description: Optional[str] = None,
) -> None:
    """
    Add an accessory requirement.

    If no catalogue product exists, the requirement remains in the
    engineering output and a warning is recorded.
    """

    quantity = safe_quantity(
        quantity
    )

    if quantity <= 0:
        return

    accessory = get_accessory(
        accessory_type
    )

    item = _create_item(
        accessory=accessory,
        accessory_type=accessory_type,
        quantity=quantity,
        category=category,
        requirement_source=requirement_source,
        description=description,
    )

    items.append(
        item
    )

    if accessory is None:

        warnings.append(
            f"No active Accessory catalogue item exists "
            f"for '{accessory_type}'. "
            f"The engineering requirement was retained."
        )

    else:

        messages.append(
            f"{quantity} × {accessory.product.name} "
            f"added to accessory requirements."
        )


# ==================================================================
# PANEL QUANTITY
# ==================================================================

def _extract_panel_quantity(
    panel_result: Any,
) -> int:
    """
    Extract installed panel quantity.
    """

    data = _selected_or_required(
        panel_result
    )

    value = _nested_value(
        data,
        (
            ("quantity",),
            ("panel_quantity",),
            ("panel_count",),
            ("number_of_panels",),
            ("total_panels",),
        ),
        default=ZERO,
    )

    return safe_quantity(
        value
    )


# ==================================================================
# PV STRING COUNT
# ==================================================================

def _extract_parallel_strings(
    panel_result: Any,
) -> int:
    """
    Extract PV parallel-string count.

    Falls back to one string when the panel engine has not exposed
    a parallel count but panels are present.
    """

    data = _selected_or_required(
        panel_result
    )

    value = _nested_value(
        data,
        (
            ("parallel_strings",),
            ("parallel_count",),
            ("strings_parallel",),
            ("pv_parallel",),
            ("parallel",),
        ),
        default=None,
    )

    if value is not None:

        strings = safe_quantity(
            value
        )

        if strings > 0:
            return strings

    panel_quantity = _extract_panel_quantity(
        panel_result
    )

    if panel_quantity > 0:
        return 1

    return 0


# ==================================================================
# BATTERY QUANTITY
# ==================================================================

def _extract_battery_quantity(
    battery_result: Any,
) -> int:
    """
    Extract total battery quantity.

    Supports both selected-product output and engineering output.
    """

    data = _selected_or_required(
        battery_result
    )

    value = _nested_value(
        data,
        (
            ("quantity",),
            ("battery_quantity",),
            ("total_batteries",),
            ("number_of_batteries",),
        ),
        default=ZERO,
    )

    return safe_quantity(
        value
    )


# ==================================================================
# BATTERY SERIES / PARALLEL
# ==================================================================

def _extract_battery_series(
    battery_result: Any,
) -> int:
    """
    Extract battery series count.
    """

    data = _selected_or_required(
        battery_result
    )

    value = _nested_value(
        data,
        (
            ("series",),
            ("series_count",),
            ("series_required",),
            ("batteries_in_series",),
        ),
        default=0,
    )

    return safe_quantity(
        value
    )


def _extract_battery_parallel(
    battery_result: Any,
) -> int:
    """
    Extract battery parallel-string count.
    """

    data = _selected_or_required(
        battery_result
    )

    value = _nested_value(
        data,
        (
            ("parallel",),
            ("parallel_count",),
            ("batteries_in_parallel",),
        ),
        default=0,
    )

    return safe_quantity(
        value
    )


# ==================================================================
# DISTANCE EXTRACTION
# ==================================================================

def _extract_distance(
    design_inputs: Any,
    *keys: str,
) -> Decimal:
    """
    Safely extract a cable-route distance.
    """

    if not isinstance(
        design_inputs,
        dict,
    ):
        return ZERO

    for key in keys:

        value = design_inputs.get(
            key
        )

        if value is not None:
            return non_negative(
                value
            )

    return ZERO


# ==================================================================
# CABLE DISTANCE
# ==================================================================

def _extract_cable_distances(
    cable_result: Any,
    design_inputs: Any,
) -> Dict[str, Decimal]:
    """
    Extract PV, battery and AC cable route distances.

    Design inputs take precedence when explicitly supplied.
    """

    pv_distance = _extract_distance(
        design_inputs,
        "pv_distance",
        "pv_cable_distance",
        "pv_route_length",
    )

    battery_distance = _extract_distance(
        design_inputs,
        "battery_distance",
        "battery_cable_distance",
        "battery_route_length",
    )

    ac_distance = _extract_distance(
        design_inputs,
        "ac_distance",
        "ac_cable_distance",
        "ac_route_length",
    )

    if isinstance(
        cable_result,
        dict,
    ):

        pv_distance = (
            pv_distance
            if pv_distance > ZERO
            else non_negative(
                _nested_value(
                    cable_result,
                    (
                        (
                            "pv",
                            "length",
                        ),
                        (
                            "pv_cable",
                            "length",
                        ),
                        (
                            "pv_cable",
                            "required",
                            "length",
                        ),
                    ),
                    default=ZERO,
                )
            )
        )

        battery_distance = (
            battery_distance
            if battery_distance > ZERO
            else non_negative(
                _nested_value(
                    cable_result,
                    (
                        (
                            "battery",
                            "length",
                        ),
                        (
                            "battery_cable",
                            "length",
                        ),
                        (
                            "battery_cable",
                            "required",
                            "length",
                        ),
                    ),
                    default=ZERO,
                )
            )
        )

        ac_distance = (
            ac_distance
            if ac_distance > ZERO
            else non_negative(
                _nested_value(
                    cable_result,
                    (
                        (
                            "ac",
                            "length",
                        ),
                        (
                            "ac_cable",
                            "length",
                        ),
                        (
                            "ac_cable",
                            "required",
                            "length",
                        ),
                    ),
                    default=ZERO,
                )
            )
        )

    return {
        "pv_distance": pv_distance,
        "battery_distance": battery_distance,
        "ac_distance": ac_distance,
    }


# ==================================================================
# INVERTER QUANTITY
# ==================================================================

def _extract_inverter_quantity(
    inverter_result: Any,
) -> int:
    """
    Extract inverter quantity.
    """

    data = _selected_or_required(
        inverter_result
    )

    value = _nested_value(
        data,
        (
            ("quantity",),
            ("inverter_quantity",),
            ("number_of_inverters",),
        ),
        default=1,
    )

    quantity = safe_quantity(
        value,
        minimum=1,
    )

    return quantity


# ==================================================================
# CONTROLLER QUANTITY
# ==================================================================

def _extract_controller_quantity(
    controller_result: Any,
) -> int:
    """
    Extract charge-controller quantity.
    """

    data = _selected_or_required(
        controller_result
    )

    value = _nested_value(
        data,
        (
            ("quantity",),
            ("controller_quantity",),
            ("number_of_controllers",),
            ("required_controllers",),
        ),
        default=1,
    )

    return safe_quantity(
        value,
        minimum=1,
    )


# ==================================================================
# ACCESSORY GENERATION
# ==================================================================

def _generate_accessories(
    *,
    battery_result: Dict[str, Any],
    panel_result: Dict[str, Any],
    inverter_result: Dict[str, Any],
    controller_result: Dict[str, Any],
    cable_result: Optional[Dict[str, Any]],
    protection_result: Optional[Dict[str, Any]],
    design_inputs: Optional[Dict[str, Any]],
    operating_mode: str,
) -> Dict[str, Any]:
    """
    Generate accessory requirements.
    """

    items: List[Dict[str, Any]] = []

    warnings: List[str] = []

    messages: List[str] = []

    # --------------------------------------------------------------
    # PRIMARY QUANTITIES
    # --------------------------------------------------------------

    panel_quantity = _extract_panel_quantity(
        panel_result
    )

    battery_quantity = _extract_battery_quantity(
        battery_result
    )

    inverter_quantity = _extract_inverter_quantity(
        inverter_result
    )

    controller_quantity = _extract_controller_quantity(
        controller_result
    )

    parallel_strings = _extract_parallel_strings(
        panel_result
    )

    battery_series = _extract_battery_series(
        battery_result
    )

    battery_parallel = _extract_battery_parallel(
        battery_result
    )

    # --------------------------------------------------------------
    # CABLE ROUTES
    # --------------------------------------------------------------

    distances = _extract_cable_distances(
        cable_result,
        design_inputs,
    )

    pv_distance = distances[
        "pv_distance"
    ]

    battery_distance = distances[
        "battery_distance"
    ]

    ac_distance = distances[
        "ac_distance"
    ]

    total_cable_distance = (
        pv_distance
        + battery_distance
        + ac_distance
    )

    # ==============================================================
    # PV ACCESSORIES
    # ==============================================================

    if panel_quantity > 0:

        # Panel clamps.
        clamp_quantity = quantity_ceiling(
            Decimal(panel_quantity)
            * DEFAULT_CLAMPS_PER_PANEL
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="clamp",
            quantity=clamp_quantity,
            category="mounting",
            requirement_source="panel_quantity",
            description=(
                "PV module mounting clamps"
            ),
        )

        # Mounting fasteners.
        bolt_quantity = quantity_ceiling(
            Decimal(panel_quantity)
            * DEFAULT_BOLTS_PER_PANEL
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="bolt",
            quantity=bolt_quantity,
            category="mounting",
            requirement_source="panel_quantity",
            description=(
                "PV mounting bolts"
            ),
        )

        nut_quantity = quantity_ceiling(
            Decimal(panel_quantity)
            * DEFAULT_NUTS_PER_PANEL
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="nut",
            quantity=nut_quantity,
            category="mounting",
            requirement_source="panel_quantity",
            description=(
                "PV mounting nuts"
            ),
        )

        washer_quantity = quantity_ceiling(
            Decimal(panel_quantity)
            * DEFAULT_WASHERS_PER_PANEL
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="washer",
            quantity=washer_quantity,
            category="mounting",
            requirement_source="panel_quantity",
            description=(
                "PV mounting washers"
            ),
        )

        # MC4 connector pairs.
        connector_quantity = max(
            int(MINIMUM_MC4_PAIRS),
            quantity_ceiling(
                Decimal(parallel_strings)
                * MC4_PAIRS_PER_STRING
            ),
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="connector",
            quantity=connector_quantity,
            category="pv",
            requirement_source="pv_parallel_strings",
            description=(
                "MC4-compatible PV connector pairs"
            ),
        )

    # ==============================================================
    # BATTERY ACCESSORIES
    # ==============================================================

    if battery_quantity > 0:

        lug_quantity = max(
            int(MINIMUM_BATTERY_LUGS),
            quantity_ceiling(
                Decimal(battery_quantity)
                * LUGS_PER_BATTERY
            ),
        )

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="lug",
            quantity=lug_quantity,
            category="cabling",
            requirement_source="battery_quantity",
            description=(
                "Battery cable lugs / terminal lugs"
            ),
        )

        # Battery rack.
        if battery_quantity > 2:

            rack_quantity = quantity_ceiling(
                Decimal(battery_quantity)
                /
                BATTERIES_PER_RACK
            )

            _add_item(
                items,
                warnings,
                messages,
                accessory_type="battery_rack",
                quantity=rack_quantity,
                category="battery",
                requirement_source="battery_quantity",
                description=(
                    "Battery rack / battery support"
                ),
            )

    # ==============================================================
    # CABLE GLANDS
    # ==============================================================

    if total_cable_distance > ZERO:

        distance_allowance = quantity_ceiling(
            total_cable_distance
            /
            Decimal("10")
        )

        gland_quantity = max(
            int(MINIMUM_CABLE_GLANDS),
            distance_allowance,
        )

    else:

        gland_quantity = int(
            MINIMUM_CABLE_GLANDS
        )

    _add_item(
        items,
        warnings,
        messages,
        accessory_type="gland",
        quantity=gland_quantity,
        category="cabling",
        requirement_source="cable_routes",
        description=(
            "Cable glands for equipment and enclosure entries"
        ),
    )

    # ==============================================================
    # TRUNKING / CONDUIT
    # ==============================================================

    """
    Trunking and conduit are deliberately NOT automatically added
    from cable distance alone.

    Cable route length does not tell us whether the installation
    is:

        - exposed
        - surface mounted
        - concealed
        - in conduit
        - in trunking
        - buried

    Automatically pricing these from distance would therefore
    create false engineering precision.

    They can be added later when installation method is supplied.
    """

    installation_type = ""

    if isinstance(
        design_inputs,
        dict,
    ):
        installation_type = str(
            design_inputs.get(
                "installation_type",
                design_inputs.get(
                    "installation_method",
                    "",
                ),
            )
            or ""
        ).lower()

    if (
        "trunk" in installation_type
        and total_cable_distance > ZERO
    ):

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="trunking",
            quantity=quantity_ceiling(
                total_cable_distance
            ),
            category="cabling",
            requirement_source="installation_type",
            description=(
                "Cable trunking"
            ),
        )

    elif (
        "conduit" in installation_type
        and total_cable_distance > ZERO
    ):

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="conduit",
            quantity=quantity_ceiling(
                total_cable_distance
            ),
            category="cabling",
            requirement_source="installation_type",
            description=(
                "Cable conduit"
            ),
        )

    # ==============================================================
    # EARTHING ACCESSORY
    # ==============================================================

    earthing_required = True

    if isinstance(
        design_inputs,
        dict,
    ):

        explicit_earthing = design_inputs.get(
            "earthing_required"
        )

        if explicit_earthing is not None:

            earthing_required = bool(
                explicit_earthing
            )

    if earthing_required:

        _add_item(
            items,
            warnings,
            messages,
            accessory_type="earthing",
            quantity=int(
                MINIMUM_EARTHING_ITEMS
            ),
            category="earthing",
            requirement_source="solar_system",
            description=(
                "PV/system earthing and bonding materials"
            ),
        )

    # ==============================================================
    # GENERAL ACCESSORY ALLOWANCE
    # ==============================================================

    """
    We do not automatically add arbitrary 'other' items.

    A professional BOQ should contain identifiable materials,
    not unexplained quantities.
    """

    # ==============================================================
    # SUMMARY
    # ==============================================================

    total_quantity = sum(
        (
            item["quantity"]
            for item in items
        ),
        0,
    )

    total_cost = sum(
        (
            to_decimal(
                item["total_price"]
            )
            for item in items
        ),
        ZERO,
    )

    return {
        "items": items,

        "panel_quantity": panel_quantity,

        "battery_quantity": battery_quantity,

        "inverter_quantity": inverter_quantity,

        "controller_quantity": controller_quantity,

        "parallel_strings": parallel_strings,

        "battery_series": battery_series,

        "battery_parallel": battery_parallel,

        "pv_distance": round_decimal(
            pv_distance
        ),

        "battery_distance": round_decimal(
            battery_distance
        ),

        "ac_distance": round_decimal(
            ac_distance
        ),

        "total_cable_distance": round_decimal(
            total_cable_distance
        ),

        "total_quantity": total_quantity,

        "total_cost": round_decimal(
            total_cost
        ),

        "operating_mode": operating_mode,
    }


# ==================================================================
# CATEGORY ORGANIZATION
# ==================================================================

def _categorize_items(
    items: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Organize accessory items by engineering category.
    """

    categories = {
        "pv": [],
        "battery": [],
        "inverter": [],
        "controller": [],
        "cabling": [],
        "mounting": [],
        "earthing": [],
        "general": [],
    }

    for item in items:

        category = item.get(
            "category",
            "general",
        )

        if category not in categories:
            category = "general"

        categories[
            category
        ].append(
            item
        )

    return categories


# ==================================================================
# REQUIREMENT SUMMARY
# ==================================================================

def _build_requirement(
    *,
    battery_result: Dict[str, Any],
    panel_result: Dict[str, Any],
    inverter_result: Dict[str, Any],
    controller_result: Dict[str, Any],
    generation: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce the stable engineering requirement section.

    This section is intentionally independent of catalogue
    availability.
    """

    return {
        "panel_quantity": generation[
            "panel_quantity"
        ],

        "array_power": number(
            _nested_value(
                _selected_or_required(
                    panel_result
                ),
                (
                    ("installed_power",),
                    ("array_power",),
                    ("required_array_power",),
                    ("recommended_array_power",),
                ),
                default=ZERO,
            )
        ),

        "battery_quantity": generation[
            "battery_quantity"
        ],

        "battery_series": generation[
            "battery_series"
        ],

        "battery_parallel": generation[
            "battery_parallel"
        ],

        "inverter_quantity": generation[
            "inverter_quantity"
        ],

        "controller_quantity": generation[
            "controller_quantity"
        ],

        "pv_parallel_strings": generation[
            "parallel_strings"
        ],

        "pv_distance": number(
            generation[
                "pv_distance"
            ]
        ),

        "battery_distance": number(
            generation[
                "battery_distance"
            ]
        ),

        "ac_distance": number(
            generation[
                "ac_distance"
            ]
        ),

        "total_cable_distance": number(
            generation[
                "total_cable_distance"
            ]
        ),

        "operating_mode": generation[
            "operating_mode"
        ],
    }


# ==================================================================
# PUBLIC ENGINE
# ==================================================================

def calculate_accessories(
    battery_result: Optional[Dict[str, Any]] = None,
    panel_result: Optional[Dict[str, Any]] = None,
    inverter_result: Optional[Dict[str, Any]] = None,
    operating_mode: str = "off_grid",
    controller_result: Optional[Dict[str, Any]] = None,
    cable_result: Optional[Dict[str, Any]] = None,
    protection_result: Optional[Dict[str, Any]] = None,
    design_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Canonical Phase 9 Accessories Engine API.

    Required core inputs
    --------------------
    battery_result
    panel_result
    inverter_result

    Optional upstream results
    -------------------------
    controller_result
    cable_result
    protection_result

    Optional design inputs
    ----------------------
    design_inputs may contain:

        {
            "pv_distance": 10,
            "battery_distance": 3,
            "ac_distance": 15,

            "installation_type": "trunking",

            "earthing_required": True,
        }

    Backward compatibility
    ----------------------
    The first four positional arguments intentionally preserve the
    API already used by the current project:

        calculate_accessories(
            battery_result,
            panel_result,
            inverter_result,
            "off_grid",
        )

    Additional upstream results may be supplied by keyword.

    This prevents positional signature breakage while allowing the
    engine to become more integrated with the full design pipeline.
    """

    warnings: List[str] = []

    messages: List[str] = []

    battery_result = (
        battery_result
        if isinstance(
            battery_result,
            dict,
        )
        else {}
    )

    panel_result = (
        panel_result
        if isinstance(
            panel_result,
            dict,
        )
        else {}
    )

    inverter_result = (
        inverter_result
        if isinstance(
            inverter_result,
            dict,
        )
        else {}
    )

    controller_result = (
        controller_result
        if isinstance(
            controller_result,
            dict,
        )
        else {}
    )

    cable_result = (
        cable_result
        if isinstance(
            cable_result,
            dict,
        )
        else {}
    )

    protection_result = (
        protection_result
        if isinstance(
            protection_result,
            dict,
        )
        else {}
    )

    design_inputs = (
        design_inputs
        if isinstance(
            design_inputs,
            dict,
        )
        else {}
    )

    # --------------------------------------------------------------
    # OPERATING MODE
    # --------------------------------------------------------------

    valid_modes = {
        "off_grid",
        "hybrid",
        "grid_tied",
        "solar_battery",
        "backup",
    }

    if operating_mode not in valid_modes:

        warnings.append(
            f"Unsupported operating mode "
            f"'{operating_mode}'. "
            f"'off_grid' was used."
        )

        operating_mode = "off_grid"

    # --------------------------------------------------------------
    # UPSTREAM VALIDATION
    # --------------------------------------------------------------

    if not battery_result:

        warnings.append(
            "Battery engineering result was not supplied. "
            "Battery-specific accessories may be incomplete."
        )

    if not panel_result:

        warnings.append(
            "Panel engineering result was not supplied. "
            "PV mounting accessories may be incomplete."
        )

    if not inverter_result:

        warnings.append(
            "Inverter engineering result was not supplied. "
            "Inverter-related accessory requirements may be incomplete."
        )

    if not controller_result:

        messages.append(
            "Charge-controller result was not supplied. "
            "No controller-specific accessory assumptions were made."
        )

    if not cable_result:

        messages.append(
            "Cable result was not supplied. "
            "Cable-route accessory quantities use supplied design "
            "distances only."
        )

    if not protection_result:

        messages.append(
            "Protection result was not supplied. "
            "Protection-device accessories are not duplicated by "
            "this engine."
        )

    # --------------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------------

    generation = _generate_accessories(
        battery_result=battery_result,
        panel_result=panel_result,
        inverter_result=inverter_result,
        controller_result=controller_result,
        cable_result=cable_result,
        protection_result=protection_result,
        design_inputs=design_inputs,
        operating_mode=operating_mode,
    )

    items = generation[
        "items"
    ]

    categories = _categorize_items(
        items
    )

    requirement = _build_requirement(
        battery_result=battery_result,
        panel_result=panel_result,
        inverter_result=inverter_result,
        controller_result=controller_result,
        generation=generation,
    )

    # --------------------------------------------------------------
    # ENGINEERING MESSAGE
    # --------------------------------------------------------------

    messages.append(
        "Accessories engineering completed successfully."
    )

    messages.append(
        f"{len(items)} accessory requirement line(s) "
        "were generated."
    )

    # --------------------------------------------------------------
    # RESULT
    # --------------------------------------------------------------

    return {
        "success": True,

        "required": requirement,

        "items": items,

        "categories": categories,

        "summary": {
            "line_count": len(items),

            "total_quantity": generation[
                "total_quantity"
            ],

            "total_cost": number(
                generation[
                    "total_cost"
                ]
            ),

            "catalogue_items_available": sum(
                1
                for item in items
                if item[
                    "availability"
                ] == "available"
            ),

            "catalogue_items_missing": sum(
                1
                for item in items
                if item[
                    "availability"
                ] == "not_in_catalogue"
            ),
        },

        "warnings": warnings,

        "messages": messages,

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,

        "message": (
            "Accessory requirements calculated successfully."
        ),
    }


# ==================================================================
# BACKWARD-COMPATIBLE LEGACY WRAPPER
# ==================================================================

def build_accessories(
    panel_quantity: Any = 0,
    battery_quantity: Any = 0,
    pv_distance: Any = 0,
    battery_distance: Any = 0,
    ac_distance: Any = 0,
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper.

    The previous project used:

        build_accessories(
            panel_quantity=...,
            battery_quantity=...,
            pv_distance=...,
            battery_distance=...,
            ac_distance=...,
        )

    This function remains available so existing code does not fail
    while the project transitions to the Phase 9 canonical API.

    It does NOT duplicate the engineering logic.

    It constructs the minimum compatible result structures and
    delegates everything to calculate_accessories().
    """

    panel_quantity = safe_quantity(
        panel_quantity
    )

    battery_quantity = safe_quantity(
        battery_quantity
    )

    design_inputs = {
        "pv_distance": non_negative(
            pv_distance
        ),

        "battery_distance": non_negative(
            battery_distance
        ),

        "ac_distance": non_negative(
            ac_distance
        ),
    }

    panel_result = {
        "success": True,

        "required": {
            "quantity": panel_quantity,
            "panel_quantity": panel_quantity,
        },

        "selected": {
            "quantity": panel_quantity,
        },
    }

    battery_result = {
        "success": True,

        "required": {
            "quantity": battery_quantity,
            "battery_quantity": battery_quantity,
        },

        "selected": {
            "quantity": battery_quantity,
        },
    }

    inverter_result = {
        "success": True,

        "required": {
            "quantity": 1,
        },

        "selected": {
            "quantity": 1,
        },
    }

    result = calculate_accessories(
        battery_result=battery_result,
        panel_result=panel_result,
        inverter_result=inverter_result,
        operating_mode="off_grid",
        design_inputs=design_inputs,
    )

    return result


# ==================================================================
# PUBLIC ALIAS
# ==================================================================

calculate_accessory_requirements = (
    calculate_accessories
)