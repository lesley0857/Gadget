"""
solar/services/boq_engine.py

PHASE 10
BILL OF QUANTITIES ENGINE

This module consolidates the engineering outputs from the completed
solar design pipeline into one standardized Bill of Quantities.

PIPELINE POSITION
-----------------

    Phase 1  Load
        ↓
    Phase 2  System Voltage
        ↓
    Phase 3  Battery
        ↓
    Phase 4  PV Array / Panels
        ↓
    Phase 5  Inverter
        ↓
    Phase 6  Charge Controller
        ↓
    Phase 7  Cables
        ↓
    Phase 8  Protection
        ↓
    Phase 9  Accessories
        ↓
    Phase 10 BOQ
        ↓
    Phase 11 Pricing

RESPONSIBILITY
--------------

This engine:

    - receives completed upstream engineering results
    - validates those results
    - extracts selected equipment
    - extracts selected cables
    - extracts protection devices
    - extracts accessories
    - normalizes all items into one BOQ structure
    - preserves engineering specifications
    - calculates line quantities
    - calculates line totals
    - groups items by engineering category
    - calculates category totals
    - produces a standardized downstream contract

This engine DOES NOT:

    - select equipment
    - size batteries
    - size PV
    - select inverters
    - select controllers
    - size cables
    - select protection
    - select accessories
    - apply installation percentage
    - apply profit
    - apply VAT
    - calculate final project selling price

Those responsibilities belong to earlier engineering engines
or the downstream Pricing Engine.

IMPORTANT
---------

The BOQ engine accepts dictionaries produced by the engineering
engines. It deliberately does not import or depend on their
internal classes.

That keeps Phase 10 decoupled from database models and prevents
signature coupling between engineering stages.
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


# ======================================================================
# ENGINE METADATA
# ======================================================================

ENGINE_NAME = "Bill of Quantities Engine"
ENGINE_VERSION = "10.0.0"


# ======================================================================
# CONSTANTS
# ======================================================================

ZERO = Decimal("0")
ONE = Decimal("1")

DEFAULT_UNIT = "pcs"

CATEGORY_BATTERY = "Battery"
CATEGORY_PANELS = "Solar Panels"
CATEGORY_INVERTER = "Inverter"
CATEGORY_CONTROLLER = "Charge Controller"
CATEGORY_CABLES = "Cables"
CATEGORY_PROTECTION = "Protection"
CATEGORY_ACCESSORIES = "Accessories"


CORE_CATEGORIES = (
    CATEGORY_BATTERY,
    CATEGORY_PANELS,
    CATEGORY_INVERTER,
    CATEGORY_CONTROLLER,
    CATEGORY_CABLES,
    CATEGORY_PROTECTION,
    CATEGORY_ACCESSORIES,
)


# ======================================================================
# DECIMAL UTILITIES
# ======================================================================

def to_decimal(
    value: Any,
    default: Decimal = ZERO,
) -> Decimal:
    """
    Safely convert any numeric value to Decimal.

    Floats are converted through str() to prevent binary floating
    point artefacts from entering engineering calculations.
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
    Return a positive Decimal.

    Zero and negative values become default.
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
    Engineering/commercial rounding helper.
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
    Convert Decimal to JSON/template-friendly numeric values.

    Whole numbers become int.
    Fractional values become float.
    """

    number = round_decimal(
        value,
        places=places,
    )

    if number == number.to_integral_value():
        return int(number)

    return float(number)


# ======================================================================
# GENERIC DICTIONARY HELPERS
# ======================================================================

def _get(
    source: Any,
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Retrieve the first available key from a dictionary.

    This deliberately supports small variations in upstream
    serialization while keeping the BOQ output canonical.
    """

    if not isinstance(source, dict):
        return default

    for key in keys:
        if key in source:
            value = source[key]

            if value is not None:
                return value

    return default


def _first_dict(
    *values: Any,
) -> Dict[str, Any]:
    """
    Return the first dictionary in a sequence.
    """

    for value in values:
        if isinstance(value, dict):
            return value

    return {}


def _clean_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Normalize textual values.
    """

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


# ======================================================================
# RESULT VALIDATION
# ======================================================================

def _result_is_successful(
    result: Optional[Dict[str, Any]],
) -> bool:
    """
    Determine whether an upstream engine result represents a
    successful engineering stage.

    Empty results are considered unavailable.
    """

    if not isinstance(result, dict):
        return False

    if result.get("success") is False:
        return False

    if result.get("status") in {
        "failed",
        "error",
        "no_solution",
        "no_compatible_controller",
        "no_compatible_inverter",
        "no_compatible_battery",
    }:
        return False

    return True


def _validate_upstream_result(
    name: str,
    result: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Validate one upstream engine result.

    Returns an error message or None.
    """

    if result is None:
        return (
            f"{name} result is required "
            "before generating the BOQ."
        )

    if not isinstance(result, dict):
        return (
            f"{name} result must be a dictionary."
        )

    if result.get("success") is False:
        message = result.get(
            "message",
            f"{name} engine did not complete successfully.",
        )

        return str(message)

    return None


# ======================================================================
# SELECTED OBJECT EXTRACTION
# ======================================================================

def _selected(
    result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Return the canonical selected object from an engine result.

    The current rebuilt engines use:

        result["selected"]

    This helper also tolerates a directly serialized selected
    dictionary for defensive compatibility.
    """

    if not isinstance(result, dict):
        return {}

    selected = result.get("selected")

    if isinstance(selected, dict):
        return selected

    return {}


# ======================================================================
# ITEM BUILDING
# ======================================================================

def _build_item(
    *,
    description: str,
    category: str,
    quantity: Any,
    unit: str = DEFAULT_UNIT,
    unit_price: Any = ZERO,
    specification: str = "",
    item_type: str = "",
    source: str = "",
    reference: Any = None,
    object_value: Any = None,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Build one canonical BOQ line.

    This is the only function that creates BOQ line items.

    Therefore every item has the same structure.
    """

    quantity_decimal = positive_decimal(
        quantity
    )

    if quantity_decimal <= ZERO:
        raise ValueError(
            f"BOQ item '{description}' must have "
            "a quantity greater than zero."
        )

    price = non_negative_decimal(
        unit_price
    )

    total_price = (
        quantity_decimal
        * price
    )

    return {
        "description": _clean_text(
            description,
            default="Unnamed item",
        ),

        "category": _clean_text(
            category,
            default="Material",
        ),

        "item_type": _clean_text(
            item_type
        ),

        "specification": _clean_text(
            specification
        ),

        "unit": _clean_text(
            unit,
            default=DEFAULT_UNIT,
        ),

        "quantity": output_number(
            quantity_decimal
        ),

        "unit_price": output_number(
            price
        ),

        "total_price": output_number(
            total_price
        ),

        "source": _clean_text(
            source
        ),

        "reference": reference,

        "object": object_value,

        "notes": _clean_text(
            notes
        ),
    }


# ======================================================================
# PRICE EXTRACTION
# ======================================================================

def _extract_unit_price(
    value: Any,
) -> Decimal:
    """
    Extract a unit price from a selected engine object.

    Supported fields:

        price
        unit_price
        selling_price
        price_per_unit
    """

    if not isinstance(value, dict):
        return ZERO

    for key in (
        "price",
        "unit_price",
        "selling_price",
        "price_per_unit",
    ):
        if key in value:
            price = to_decimal(
                value.get(key)
            )

            if price >= ZERO:
                return price

    return ZERO


def _extract_total_price(
    value: Any,
) -> Decimal:
    """
    Extract an already calculated total price when available.
    """

    if not isinstance(value, dict):
        return ZERO

    return non_negative_decimal(
        value.get(
            "total_price",
            ZERO,
        )
    )


# ======================================================================
# BATTERY
# ======================================================================

def _build_battery_item(
    battery_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Convert the selected battery configuration into one BOQ line.
    """

    selected = _selected(
        battery_result
    )

    if not selected:
        return None

    quantity = _get(
        selected,
        "quantity",
        "battery_quantity",
        default=0,
    )

    if to_decimal(quantity) <= ZERO:
        return None

    battery = _first_dict(
        selected.get("battery"),
        selected.get("product"),
        selected.get("equipment"),
    )

    name = _get(
        selected,
        "name",
        default=None,
    )

    if not name:
        name = _get(
            battery,
            "name",
            "model",
            default="Battery",
        )

    brand = _get(
        selected,
        "brand",
        default=None,
    )

    if not brand:
        brand = _get(
            battery,
            "brand",
            default="",
        )

    model = _get(
        selected,
        "model",
        default=None,
    )

    if not model:
        model = _get(
            battery,
            "model",
            default="",
        )

    battery_voltage = _get(
        selected,
        "battery_voltage",
        "voltage",
        "nominal_voltage",
        default=None,
    )

    capacity = _get(
        selected,
        "capacity_ah",
        "capacity",
        default=None,
    )

    battery_type = _get(
        selected,
        "battery_type",
        "type",
        default=None,
    )

    specification_parts = []

    if brand:
        specification_parts.append(
            str(brand)
        )

    if model:
        specification_parts.append(
            str(model)
        )

    if battery_type:
        specification_parts.append(
            str(battery_type)
        )

    if battery_voltage:
        specification_parts.append(
            f"{battery_voltage} V"
        )

    if capacity:
        specification_parts.append(
            f"{capacity} Ah"
        )

    specification = " / ".join(
        specification_parts
    )

    unit_price = _extract_unit_price(
        selected
    )

    return _build_item(
        description=str(name),
        category=CATEGORY_BATTERY,
        item_type="battery",
        specification=specification,
        unit="pcs",
        quantity=quantity,
        unit_price=unit_price,
        source="Battery Engine",
        object_value=battery or None,
    )


# ======================================================================
# PV PANELS
# ======================================================================

def _build_panel_item(
    panel_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Convert the selected PV module configuration into one BOQ line.
    """

    selected = _selected(
        panel_result
    )

    if not selected:
        return None

    quantity = _get(
        selected,
        "quantity",
        "panel_quantity",
        "module_quantity",
        "count",
        default=0,
    )

    if to_decimal(quantity) <= ZERO:
        return None

    panel = _first_dict(
        selected.get("panel"),
        selected.get("module"),
        selected.get("product"),
        selected.get("equipment"),
    )

    name = _get(
        selected,
        "name",
        default=None,
    )

    if not name:
        name = _get(
            panel,
            "name",
            "model",
            default="Solar PV Module",
        )

    brand = _get(
        selected,
        "brand",
        default=None,
    )

    if not brand:
        brand = _get(
            panel,
            "brand",
            default="",
        )

    model = _get(
        selected,
        "model",
        default=None,
    )

    if not model:
        model = _get(
            panel,
            "model",
            default="",
        )

    power = _get(
        selected,
        "power",
        "wattage",
        "power_w",
        "module_power",
        "rated_power",
        default=None,
    )

    specification_parts = []

    if brand:
        specification_parts.append(
            str(brand)
        )

    if model:
        specification_parts.append(
            str(model)
        )

    if power:
        specification_parts.append(
            f"{power} W"
        )

    specification = " / ".join(
        specification_parts
    )

    unit_price = _extract_unit_price(
        selected
    )

    return _build_item(
        description=str(name),
        category=CATEGORY_PANELS,
        item_type="pv_module",
        specification=specification,
        unit="pcs",
        quantity=quantity,
        unit_price=unit_price,
        source="Panel Engine",
        object_value=panel or None,
    )


# ======================================================================
# INVERTER
# ======================================================================

def _build_inverter_item(
    inverter_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Convert selected inverter configuration into a BOQ line.
    """

    selected = _selected(
        inverter_result
    )

    if not selected:
        return None

    quantity = _get(
        selected,
        "quantity",
        "count",
        default=1,
    )

    inverter = _first_dict(
        selected.get("inverter"),
        selected.get("product"),
        selected.get("equipment"),
    )

    name = _get(
        selected,
        "name",
        default=None,
    )

    if not name:
        name = _get(
            inverter,
            "name",
            "model",
            default="Inverter",
        )

    brand = _get(
        selected,
        "brand",
        default=None,
    )

    if not brand:
        brand = _get(
            inverter,
            "brand",
            default="",
        )

    model = _get(
        selected,
        "model",
        default=None,
    )

    if not model:
        model = _get(
            inverter,
            "model",
            default="",
        )

    rated_power = _get(
        selected,
        "rated_power",
        "supported_power",
        "power",
        "power_w",
        default=None,
    )

    battery_voltage = _get(
        selected,
        "battery_voltage",
        "dc_voltage",
        default=None,
    )

    output_voltage = _get(
        selected,
        "output_voltage",
        "ac_voltage",
        default=None,
    )

    specification_parts = []

    if brand:
        specification_parts.append(
            str(brand)
        )

    if model:
        specification_parts.append(
            str(model)
        )

    if rated_power:
        specification_parts.append(
            f"{rated_power} W"
        )

    if battery_voltage:
        specification_parts.append(
            f"DC {battery_voltage} V"
        )

    if output_voltage:
        specification_parts.append(
            f"AC {output_voltage} V"
        )

    specification = " / ".join(
        specification_parts
    )

    unit_price = _extract_unit_price(
        selected
    )

    return _build_item(
        description=str(name),
        category=CATEGORY_INVERTER,
        item_type="inverter",
        specification=specification,
        unit="pcs",
        quantity=quantity,
        unit_price=unit_price,
        source="Inverter Engine",
        object_value=inverter or None,
    )


# ======================================================================
# CHARGE CONTROLLER
# ======================================================================

def _build_controller_item(
    controller_result: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Convert selected MPPT/charge-controller configuration into
    a BOQ line.
    """

    selected = _selected(
        controller_result
    )

    if not selected:
        return None

    quantity = _get(
        selected,
        "quantity",
        "count",
        default=1,
    )

    controller = _first_dict(
        selected.get("controller"),
        selected.get("product"),
        selected.get("equipment"),
    )

    name = _get(
        selected,
        "name",
        default=None,
    )

    if not name:
        name = _get(
            controller,
            "name",
            "model",
            default="Charge Controller",
        )

    brand = _get(
        selected,
        "brand",
        default=None,
    )

    if not brand:
        brand = _get(
            controller,
            "brand",
            default="",
        )

    model = _get(
        selected,
        "model",
        default=None,
    )

    if not model:
        model = _get(
            controller,
            "model",
            default="",
        )

    charge_current = _get(
        selected,
        "charge_current",
        "max_charge_current",
        "total_charge_current",
        default=None,
    )

    pv_voltage = _get(
        selected,
        "max_pv_voltage",
        "pv_voltage",
        default=None,
    )

    pv_power = _get(
        selected,
        "controller_power",
        "total_controller_power",
        "pv_power",
        default=None,
    )

    specification_parts = []

    if brand:
        specification_parts.append(
            str(brand)
        )

    if model:
        specification_parts.append(
            str(model)
        )

    if charge_current:
        specification_parts.append(
            f"{charge_current} A"
        )

    if pv_voltage:
        specification_parts.append(
            f"PV {pv_voltage} V"
        )

    if pv_power:
        specification_parts.append(
            f"{pv_power} W PV"
        )

    specification = " / ".join(
        specification_parts
    )

    unit_price = _extract_unit_price(
        selected
    )

    return _build_item(
        description=str(name),
        category=CATEGORY_CONTROLLER,
        item_type="charge_controller",
        specification=specification,
        unit="pcs",
        quantity=quantity,
        unit_price=unit_price,
        source="Controller Engine",
        object_value=controller or None,
    )


# ======================================================================
# CABLES
# ======================================================================

def _extract_cable_items(
    cable_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract all selected cable circuits from the cable-engine result.

    Supported canonical circuits:

        battery
        pv
        ac
        earth

    The engine also supports common aliases used by earlier
    implementations.
    """

    items: List[Dict[str, Any]] = []

    if not isinstance(
        cable_result,
        dict,
    ):
        return items

    selected = cable_result.get(
        "selected"
    )

    selected_root = (
        selected
        if isinstance(selected, dict)
        else {}
    )

    circuit_aliases = {
        "battery": (
            "battery",
            "battery_cable",
            "battery_cable_result",
        ),
        "pv": (
            "pv",
            "pv_cable",
            "pv_cable_result",
            "solar",
            "solar_cable",
        ),
        "ac": (
            "ac",
            "ac_cable",
            "ac_cable_result",
        ),
        "earth": (
            "earth",
            "earth_cable",
            "earth_cable_result",
            "ground",
        ),
    }

    for circuit, aliases in circuit_aliases.items():

        circuit_result = None

        for alias in aliases:

            candidate = cable_result.get(
                alias
            )

            if isinstance(
                candidate,
                dict,
            ):
                circuit_result = candidate
                break

            candidate = selected_root.get(
                alias
            )

            if isinstance(
                candidate,
                dict,
            ):
                circuit_result = candidate
                break

        if not circuit_result:
            continue

        circuit_selected = _selected(
            circuit_result
        )

        if not circuit_selected:

            # Some cable engines expose the selected cable
            # directly rather than under "selected".
            if any(
                key in circuit_result
                for key in (
                    "size_mm2",
                    "size",
                    "length",
                    "price",
                    "price_per_meter",
                )
            ):
                circuit_selected = circuit_result

        if not circuit_selected:
            continue

        length = _get(
            circuit_selected,
            "length",
            "required_length",
            "length_m",
            "quantity",
            default=0,
        )

        if to_decimal(length) <= ZERO:
            continue

        size = _get(
            circuit_selected,
            "size_mm2",
            "size",
            "cross_section",
            "cross_sectional_area",
            default=None,
        )

        cable_type = _get(
            circuit_selected,
            "cable_type",
            "type",
            default=None,
        )

        voltage_rating = _get(
            circuit_selected,
            "voltage_rating",
            "rated_voltage",
            default=None,
        )

        ampacity = _get(
            circuit_selected,
            "ampacity",
            "current_capacity",
            "current_rating",
            default=None,
        )

        name = _get(
            circuit_selected,
            "name",
            "description",
            default=None,
        )

        if not name:
            name = (
                f"{circuit.title()} Cable"
            )

        specification_parts = []

        if cable_type:
            specification_parts.append(
                str(cable_type)
            )

        if size:
            specification_parts.append(
                f"{size} mm²"
            )

        if ampacity:
            specification_parts.append(
                f"{ampacity} A"
            )

        if voltage_rating:
            specification_parts.append(
                f"{voltage_rating} V"
            )

        specification = " / ".join(
            specification_parts
        )

        unit_price = _extract_unit_price(
            circuit_selected
        )

        # Cable prices are normally per metre.
        unit = _get(
            circuit_selected,
            "unit",
            default="m",
        )

        items.append(
            _build_item(
                description=str(name),
                category=CATEGORY_CABLES,
                item_type=f"{circuit}_cable",
                specification=specification,
                unit=str(unit),
                quantity=length,
                unit_price=unit_price,
                source="Cable Engine",
                object_value=circuit_selected,
            )
        )

    return items


# ======================================================================
# PROTECTION
# ======================================================================

def _extract_protection_items(
    protection_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract all protection devices from the Phase 8 result.

    The engine deliberately supports both:

        protection_result["selected"]

    and the individual named protection outputs commonly used
    by the protection stage.
    """

    items: List[Dict[str, Any]] = []

    if not isinstance(
        protection_result,
        dict,
    ):
        return items

    selected_root = protection_result.get(
        "selected"
    )

    if not isinstance(
        selected_root,
        dict,
    ):
        selected_root = {}

    aliases = {
        "PV Fuse": (
            "pv_fuse",
            "pv_fuse_result",
            "fuse",
        ),
        "Battery Breaker": (
            "battery_breaker",
            "battery_breaker_result",
            "dc_breaker",
        ),
        "AC Breaker": (
            "ac_breaker",
            "ac_breaker_result",
        ),
        "DC SPD": (
            "dc_spd",
            "dc_spd_result",
        ),
        "AC SPD": (
            "ac_spd",
            "ac_spd_result",
        ),
        "PV Isolator": (
            "pv_isolator",
            "pv_isolator_result",
        ),
        "AC Isolator": (
            "ac_isolator",
            "ac_isolator_result",
        ),
    }

    for default_name, keys in aliases.items():

        selected = None

        for key in keys:

            candidate = protection_result.get(
                key
            )

            if isinstance(
                candidate,
                dict,
            ):
                selected = _selected(
                    candidate
                )

                if not selected:
                    selected = candidate

                break

            candidate = selected_root.get(
                key
            )

            if isinstance(
                candidate,
                dict,
            ):
                selected = _selected(
                    candidate
                )

                if not selected:
                    selected = candidate

                break

        if not selected:
            continue

        quantity = _get(
            selected,
            "quantity",
            "count",
            default=1,
        )

        if to_decimal(quantity) <= ZERO:
            continue

        name = _get(
            selected,
            "name",
            "description",
            default=default_name,
        )

        specification_parts = []

        voltage = _get(
            selected,
            "voltage",
            "rated_voltage",
            "voltage_rating",
            default=None,
        )

        current = _get(
            selected,
            "current",
            "rated_current",
            "rating",
            default=None,
        )

        poles = _get(
            selected,
            "poles",
            "number_of_poles",
            default=None,
        )

        if voltage:
            specification_parts.append(
                f"{voltage} V"
            )

        if current:
            specification_parts.append(
                f"{current} A"
            )

        if poles:
            specification_parts.append(
                f"{poles}P"
            )

        specification = " / ".join(
            specification_parts
        )

        unit_price = _extract_unit_price(
            selected
        )

        items.append(
            _build_item(
                description=str(name),
                category=CATEGORY_PROTECTION,
                item_type=(
                    default_name
                    .lower()
                    .replace(" ", "_")
                ),
                specification=specification,
                unit="pcs",
                quantity=quantity,
                unit_price=unit_price,
                source="Protection Engine",
                object_value=selected,
            )
        )

    return items


# ======================================================================
# ACCESSORIES
# ======================================================================

def _extract_accessory_items(
    accessory_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Convert the Phase 9 accessory output into canonical BOQ lines.
    """

    items: List[Dict[str, Any]] = []

    if not isinstance(
        accessory_result,
        dict,
    ):
        return items

    collections = []

    for key in (
        "items",
        "accessories",
        "pv_accessories",
        "battery_accessories",
        "inverter_accessories",
        "installation_accessories",
        "mounting_accessories",
        "mounting",
    ):

        value = accessory_result.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            collections.extend(
                value
            )

    # Avoid duplicates when an engine exposes the same list
    # through more than one alias.
    seen = set()

    for accessory in collections:

        if not isinstance(
            accessory,
            dict,
        ):
            continue

        identity = (
            accessory.get("name"),
            accessory.get("type"),
            accessory.get("quantity"),
        )

        if identity in seen:
            continue

        seen.add(identity)

        quantity = _get(
            accessory,
            "quantity",
            "count",
            default=1,
        )

        if to_decimal(quantity) <= ZERO:
            continue

        name = _get(
            accessory,
            "name",
            "description",
            default="Accessory",
        )

        accessory_type = _get(
            accessory,
            "type",
            "accessory_type",
            default="accessory",
        )

        unit = _get(
            accessory,
            "unit",
            default="pcs",
        )

        unit_price = _extract_unit_price(
            accessory
        )

        # If the upstream accessory engine already calculated a
        # total, retain it only when unit price is unavailable.
        if unit_price <= ZERO:

            total_price = _extract_total_price(
                accessory
            )

            if (
                total_price > ZERO
                and
                to_decimal(quantity) > ZERO
            ):
                unit_price = (
                    total_price
                    /
                    to_decimal(quantity)
                )

        items.append(
            _build_item(
                description=str(name),
                category=CATEGORY_ACCESSORIES,
                item_type=str(
                    accessory_type
                ),
                specification=_clean_text(
                    accessory.get(
                        "specification",
                        "",
                    )
                ),
                unit=str(unit),
                quantity=quantity,
                unit_price=unit_price,
                source="Accessories Engine",
                object_value=accessory.get(
                    "object"
                ),
            )
        )

    return items


# ======================================================================
# CATEGORY BUILDERS
# ======================================================================

def _build_all_items(
    *,
    battery_result: Dict[str, Any],
    panel_result: Dict[str, Any],
    controller_result: Dict[str, Any],
    inverter_result: Dict[str, Any],
    protection_result: Dict[str, Any],
    cable_result: Dict[str, Any],
    accessory_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build the complete engineering BOQ.
    """

    items: List[Dict[str, Any]] = []

    battery = _build_battery_item(
        battery_result
    )

    if battery:
        items.append(
            battery
        )

    panel = _build_panel_item(
        panel_result
    )

    if panel:
        items.append(
            panel
        )

    inverter = _build_inverter_item(
        inverter_result
    )

    if inverter:
        items.append(
            inverter
        )

    controller = _build_controller_item(
        controller_result
    )

    if controller:
        items.append(
            controller
        )

    items.extend(
        _extract_cable_items(
            cable_result
        )
    )

    items.extend(
        _extract_protection_items(
            protection_result
        )
    )

    items.extend(
        _extract_accessory_items(
            accessory_result
        )
    )

    # Add final sequential line numbers.
    for index, item in enumerate(
        items,
        start=1,
    ):
        item["line_number"] = index

    return items


# ======================================================================
# CATEGORY SUMMARY
# ======================================================================

def _calculate_category_summary(
    items: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate quantity and monetary totals by BOQ category.
    """

    summary = {
        category: {
            "line_count": 0,
            "total_quantity": ZERO,
            "total_price": ZERO,
        }
        for category in CORE_CATEGORIES
    }

    for item in items:

        category = item.get(
            "category",
            "Material",
        )

        if category not in summary:

            summary[category] = {
                "line_count": 0,
                "total_quantity": ZERO,
                "total_price": ZERO,
            }

        summary[category][
            "line_count"
        ] += 1

        summary[category][
            "total_quantity"
        ] += to_decimal(
            item.get(
                "quantity",
                ZERO,
            )
        )

        summary[category][
            "total_price"
        ] += to_decimal(
            item.get(
                "total_price",
                ZERO,
            )
        )

    result = {}

    for category, values in summary.items():

        result[category] = {
            "line_count": values[
                "line_count"
            ],

            "total_quantity": output_number(
                values[
                    "total_quantity"
                ]
            ),

            "total_price": output_number(
                values[
                    "total_price"
                ]
            ),
        }

    return result


# ======================================================================
# TOTALS
# ======================================================================

def _calculate_totals(
    items: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calculate BOQ totals.
    """

    total_quantity = ZERO
    total_price = ZERO

    for item in items:

        total_quantity += to_decimal(
            item.get(
                "quantity",
                ZERO,
            )
        )

        total_price += to_decimal(
            item.get(
                "total_price",
                ZERO,
            )
        )

    return {
        "line_count": len(
            list(items)
        ) if not isinstance(
            items,
            list,
        ) else len(items),

        "total_quantity": output_number(
            total_quantity
        ),

        "total_price": output_number(
            total_price
        ),
    }


# ======================================================================
# ENGINEERING SUMMARY
# ======================================================================

def _build_engineering_summary(
    *,
    battery_result: Dict[str, Any],
    panel_result: Dict[str, Any],
    controller_result: Dict[str, Any],
    inverter_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Preserve the principal engineering selections required for
    BOQ interpretation without re-running any engineering.
    """

    battery = _selected(
        battery_result
    )

    panel = _selected(
        panel_result
    )

    controller = _selected(
        controller_result
    )

    inverter = _selected(
        inverter_result
    )

    return {
        "battery_quantity": output_number(
            _get(
                battery,
                "quantity",
                default=ZERO,
            )
        ),

        "panel_quantity": output_number(
            _get(
                panel,
                "quantity",
                default=ZERO,
            )
        ),

        "controller_quantity": output_number(
            _get(
                controller,
                "quantity",
                default=ZERO,
            )
        ),

        "inverter_quantity": output_number(
            _get(
                inverter,
                "quantity",
                default=ZERO,
            )
        ),

        "battery_model": _clean_text(
            _get(
                battery,
                "model",
                default="",
            )
        ),

        "panel_model": _clean_text(
            _get(
                panel,
                "model",
                default="",
            )
        ),

        "controller_model": _clean_text(
            _get(
                controller,
                "model",
                default="",
            )
        ),

        "inverter_model": _clean_text(
            _get(
                inverter,
                "model",
                default="",
            )
        ),
    }


# ======================================================================
# WARNINGS
# ======================================================================

def _generate_warnings(
    *,
    items: List[Dict[str, Any]],
    category_summary: Dict[str, Dict[str, Any]],
) -> List[str]:
    """
    Generate commercial/BOQ integrity warnings.

    These are not electrical design warnings.
    """

    warnings: List[str] = []

    if not items:
        warnings.append(
            "The BOQ contains no material lines."
        )

        return warnings

    zero_price_items = [
        item
        for item in items
        if to_decimal(
            item.get(
                "unit_price",
                ZERO,
            )
        ) <= ZERO
    ]

    if zero_price_items:

        warnings.append(
            f"{len(zero_price_items)} BOQ item(s) "
            "do not have a catalogue price."
        )

    for item in items:

        quantity = to_decimal(
            item.get(
                "quantity",
                ZERO,
            )
        )

        if quantity <= ZERO:
            warnings.append(
                f"BOQ item '{item.get('description', 'Unknown')}' "
                "has an invalid quantity."
            )

    return warnings


# ======================================================================
# MAIN ENGINE
# ======================================================================

def calculate_boq(
    *,
    battery_result: Optional[Dict[str, Any]],
    panel_result: Optional[Dict[str, Any]],
    controller_result: Optional[Dict[str, Any]],
    inverter_result: Optional[Dict[str, Any]],
    protection_result: Optional[Dict[str, Any]],
    cable_result: Optional[Dict[str, Any]],
    accessory_result: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Complete Phase 10 BOQ entry point.

    IMPORTANT:

    The keyword-only signature intentionally matches the rebuilt
    design pipeline:

        calculate_boq(
            battery_result=...,
            panel_result=...,
            controller_result=...,
            inverter_result=...,
            protection_result=...,
            cable_result=...,
            accessory_result=...,
        )

    No upstream engine is called from here.
    """

    upstream_results = {
        "Battery": battery_result,
        "Panel": panel_result,
        "Charge Controller": controller_result,
        "Inverter": inverter_result,
        "Protection": protection_result,
        "Cable": cable_result,
        "Accessories": accessory_result,
    }

    errors = []

    for name, result in upstream_results.items():

        error = _validate_upstream_result(
            name,
            result,
        )

        if error:
            errors.append(
                error
            )

    if errors:

        return {
            "success": False,
            "status": "invalid_upstream_results",
            "items": [],
            "categories": {},
            "category_summary": {},
            "totals": {
                "line_count": 0,
                "total_quantity": 0,
                "total_price": 0,
            },
            "engineering_summary": {},
            "warnings": [],
            "messages": [],
            "errors": errors,
            "message": (
                "BOQ generation could not be completed "
                "because one or more upstream engineering "
                "results are invalid."
            ),
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
        }

    # --------------------------------------------------------------
    # BUILD ITEMS
    # --------------------------------------------------------------

    try:

        items = _build_all_items(
            battery_result=battery_result,
            panel_result=panel_result,
            controller_result=controller_result,
            inverter_result=inverter_result,
            protection_result=protection_result,
            cable_result=cable_result,
            accessory_result=accessory_result,
        )

    except (
        TypeError,
        ValueError,
        InvalidOperation,
    ) as exc:

        return {
            "success": False,
            "status": "boq_generation_error",
            "items": [],
            "categories": {},
            "category_summary": {},
            "totals": {
                "line_count": 0,
                "total_quantity": 0,
                "total_price": 0,
            },
            "engineering_summary": {},
            "warnings": [],
            "messages": [],
            "errors": [
                str(exc)
            ],
            "message": (
                "An error occurred while constructing "
                "the Bill of Quantities."
            ),
            "engine": ENGINE_NAME,
            "engine_version": ENGINE_VERSION,
        }

    # --------------------------------------------------------------
    # CATEGORY SUMMARY
    # --------------------------------------------------------------

    category_summary = (
        _calculate_category_summary(
            items
        )
    )

    # --------------------------------------------------------------
    # CATEGORY ITEM MAP
    # --------------------------------------------------------------

    categories: Dict[
        str,
        List[Dict[str, Any]]
    ] = {
        category: []
        for category in CORE_CATEGORIES
    }

    for item in items:

        category = item.get(
            "category",
            "Material",
        )

        categories.setdefault(
            category,
            [],
        ).append(
            item
        )

    # --------------------------------------------------------------
    # TOTALS
    # --------------------------------------------------------------

    total_quantity = sum(
        (
            to_decimal(
                item.get(
                    "quantity",
                    ZERO,
                )
            )
            for item in items
        ),
        ZERO,
    )

    total_price = sum(
        (
            to_decimal(
                item.get(
                    "total_price",
                    ZERO,
                )
            )
            for item in items
        ),
        ZERO,
    )

    totals = {
        "line_count": len(items),
        "total_quantity": output_number(
            total_quantity
        ),
        "total_price": output_number(
            total_price
        ),
    }

    # --------------------------------------------------------------
    # ENGINEERING SUMMARY
    # --------------------------------------------------------------

    engineering_summary = (
        _build_engineering_summary(
            battery_result=battery_result,
            panel_result=panel_result,
            controller_result=controller_result,
            inverter_result=inverter_result,
        )
    )

    # --------------------------------------------------------------
    # WARNINGS
    # --------------------------------------------------------------

    warnings = _generate_warnings(
        items=items,
        category_summary=category_summary,
    )

    # --------------------------------------------------------------
    # MESSAGES
    # --------------------------------------------------------------

    messages = [
        (
            f"BOQ generated successfully with "
            f"{len(items)} material line(s)."
        )
    ]

    # --------------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------------

    return {
        "success": True,

        "status": "complete",

        "items": items,

        "categories": categories,

        "category_summary": category_summary,

        "totals": totals,

        "engineering_summary": engineering_summary,

        "warnings": warnings,

        "messages": messages,

        "errors": [],

        "message": (
            "Bill of Quantities generated successfully."
        ),

        "engine": ENGINE_NAME,

        "engine_version": ENGINE_VERSION,
    }


# ======================================================================
# PUBLIC ALIAS
# ======================================================================

generate_boq = calculate_boq