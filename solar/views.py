"""
solar/views.py

Application layer for the rebuilt Solar PV Design workflow.

This module does not perform engineering calculations itself.
It validates user input, assembles the canonical inputs expected by
the rebuilt service engines, persists JSON-safe results, and exposes
project/result/history/version management.

Pipeline
--------
Load
 -> System Voltage
 -> Battery
 -> PV Array
 -> Charge Controller
 -> Inverter
 -> Protection
 -> Cables
 -> Accessories
 -> BOQ
 -> Pricing
 -> Warnings
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import Decimal
from functools import lru_cache
from inspect import Parameter, signature
from typing import Any, Dict, Iterable

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from catalog.models import ProductListing
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import (
    ApplianceLoadForm,
    BatteryPreferenceForm,
    DesignRequirementsForm,
    SolarDesignForm,
    LoadItemFormSet,
)
from .models import (
    Appliance,
    DesignSetting,
    SolarDesign,
    SolarDesignVersion,
    EarthingDesign,
    ServiceRequest,
)
from .services import product_bridge
from .services.earthing_engine import design as calculate_earthing_design

from .services.load_engine import calculate_load
from .services.system_voltage_engine import determine_system_voltage
from .services.battery_engine import calculate_battery_bank, calculate_battery_system

# Phase 4 naming in the rebuilt project has existed as both
# calculate_panel_array and calculate_panels during development.
# The view resolves the public rebuilt entry point without changing
# the engine contract.
try:
    from .services.panel_engine import calculate_panel_array
except ImportError:  # pragma: no cover - compatibility with current module name
    from .services.panel_engine import calculate_panels as calculate_panel_array
    from .services.panel_engine import calculate_pv_array

from .services.controller_selection_engine import calculate_charge_controller
from .services.inverter_engine import calculate_inverter
from .services.protection_engine import calculate_protection
from .services.cable_engine import calculate_cables
from .services.accessories_engine import calculate_accessories
from .services.boq_engine import generate_boq
from .services.pricing_engine import calculate_pricing
from .services.warning_engine import calculate_warnings

try:
    from .services.warning_engine import build_warnings
except ImportError:  # Warning engine remains optional at import time.
    build_warnings = None


ENGINE_KEYS = (
    "load_result",
    "voltage_result",
    "battery_result",
    "panel_result",
    "controller_result",
    "inverter_result",
    "protection_result",
    "cable_result",
    "accessory_result",
    "boq_result",
    "pricing_result",
    "warnings_result",
)


def tool_in_progress(request: HttpRequest):
    return render(request, "solar/tool_in_progress.html")


# ---------------------------------------------------------------------
# JSON / ENGINE RESULT NORMALIZATION
# ---------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """Convert engine output into values accepted by Django JSONField."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    if is_dataclass(value):
        return _json_safe(asdict(value))

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]

    # Django model instances may appear inside dataclass candidates.
    if hasattr(value, "_meta"):
        return str(value)

    # Decimal-like numeric objects.
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _engine_success(
    result: Any,
    engine_name: str,
    *,
    allow_catalogue_gap: bool = False,
) -> None:
    """Fail for invalid engineering inputs, but retain missing catalogue items."""

    if not isinstance(result, dict):
        return

    if result.get("success") is False:
        message = (
            result.get("message")
            or result.get("error")
            or f"{engine_name} could not produce a valid result."
        )
        if allow_catalogue_gap:
            warnings = result.setdefault("warnings", [])
            warning = f"{engine_name}: {message} A quote can still be requested."
            if warning not in warnings:
                warnings.append(warning)
            return
        raise ValueError(str(message))


def _solar_transport_item(boq_items: list[dict[str, Any]], project_location: str) -> dict[str, Any] | None:
    """Quote delivery with checkout's vendor-distance and live rate logic."""
    from logistics.utils import estimate_cart_shipping_fee, lookup_city, lookup_state_centroid

    location = str(project_location or "").strip()
    coordinates = lookup_city(location) if location else None
    if not coordinates and location:
        for part in location.replace(",", " ").replace("-", " ").split():
            coordinates = lookup_city(part) or lookup_state_centroid(part)
            if coordinates:
                break
        if not coordinates:
            coordinates = lookup_state_centroid(location)
    if not coordinates:
        return None

    quantities_by_listing: dict[int, Decimal] = {}
    for item in boq_items:
        if not isinstance(item, dict) or item.get("item_type") == "transport":
            continue
        component = item.get("object")
        if not isinstance(component, dict):
            continue
        try:
            listing_id = int(component.get("id"))
        except (TypeError, ValueError):
            continue
        quantities_by_listing[listing_id] = quantities_by_listing.get(listing_id, Decimal("0")) + Decimal(str(item.get("quantity", 1) or 1))
    if not quantities_by_listing:
        return None

    listings = list(ProductListing.objects.filter(pk__in=quantities_by_listing).select_related("vendor"))
    vendors_by_id = {listing.vendor_id: listing.vendor for listing in listings}
    if not vendors_by_id:
        return None
    total_weight = sum(
        (Decimal(str(listing.weight or 0)) * quantities_by_listing.get(listing.pk, Decimal("1")) for listing in listings),
        Decimal("0"),
    )
    quote = estimate_cart_shipping_fee(
        list(vendors_by_id.values()),
        coordinates[0],
        coordinates[1],
        float(max(total_weight, Decimal("1"))),
    )
    cost = Decimal(str(quote["total"]))
    distance = float(quote["distance_km"])
    vendor_name = quote.get("farthest_vendor") or "Selected product vendor"
    return {
        "description": f"Solar delivery from {vendor_name} ({distance:.1f} km)",
        "category": "Transport",
        "item_type": "transport",
        "specification": f"Checkout logistics quote · {distance:.1f} km",
        "unit": "trip",
        "quantity": 1,
        "unit_price": float(cost),
        "total_price": float(cost),
        "source": "Checkout Logistics Calculator",
        "reference": None,
        "object": _json_safe(quote),
        "notes": f"Live logistics rate for {distance:.1f} km from selected product vendor(s) to {location}.",
    }

def _generator_option(inverter_result: Any) -> dict[str, Any] | None:
    if not isinstance(inverter_result, dict):
        return None
    option = inverter_result.get("solar_generator_option")
    return option if isinstance(option, dict) else None


def _selected_generator(inverter_result: Any) -> dict[str, Any] | None:
    option = _generator_option(inverter_result)
    if not option or option.get("available") is False:
        return None
    selected = option.get("selected_generator")
    if isinstance(selected, dict):
        return selected
    return option if option.get("product_id") else None


def _apply_generator_only_boq(boq: dict[str, Any], inverter_result: Any) -> None:
    """Replace component lines with the selected integrated generator line."""
    option = _generator_option(inverter_result)
    if option is None:
        return
    generator = _selected_generator(inverter_result)
    items: list[dict[str, Any]] = []
    if generator:
        try:
            unit_price = max(Decimal("0"), Decimal(str(generator.get("price", generator.get("unit_price", 0)) or 0)))
        except Exception:
            unit_price = Decimal("0")
        name = " ".join(str(part).strip() for part in (generator.get("brand"), generator.get("name") or generator.get("model")) if part).strip() or "Solar Generator"
        items.append({
            "description": name,
            "category": "Solar Generator",
            "item_type": "solar_generator",
            "specification": f"Integrated solar generator · {generator.get('inverter_rated_power', generator.get('rated_power_w', ''))} W inverter · {generator.get('battery_capacity_kwh', '')} kWh storage",
            "unit": "unit",
            "quantity": 1,
            "unit_price": float(unit_price),
            "total_price": float(unit_price),
            "source": "Solar Generator Catalogue",
            "reference": generator.get("product_id") or generator.get("id"),
            "object": {"id": generator.get("product_id") or generator.get("id")},
            "notes": generator.get("note", "Integrated solar generator selected for this design."),
            "line_number": 1,
        })
    boq["items"] = items
    total_price = sum((Decimal(str(item.get("total_price", 0) or 0)) for item in items), Decimal("0"))
    boq.setdefault("totals", {})
    boq["totals"].update({"line_count": len(items), "total_quantity": len(items), "total_price": float(total_price)})
    boq["categories"] = {"Solar Generator": items} if items else {}
    boq["category_summary"] = {"Solar Generator": {"line_count": len(items), "total_quantity": len(items), "total_price": float(total_price)}} if items else {}

def _system_voltage(result: Dict[str, Any]) -> Decimal:
    """Extract the canonical system voltage from the voltage engine result."""

    value = result.get("system_voltage")

    if value is None:
        value = result.get("selected_voltage")

    if value is None:
        requirement = result.get("requirement") or {}
        value = requirement.get("system_voltage")

    try:
        value = Decimal(str(value))
    except (TypeError, ValueError):
        value = Decimal("0")

    if value <= 0:
        raise ValueError("The system voltage engine returned an invalid voltage.")

    return value


# ---------------------------------------------------------------------
# ENGINE CALL ADAPTER
# ---------------------------------------------------------------------

@lru_cache(maxsize=None)
def _accepted_parameters(function):
    """
    Cache the public signature of an engine function.

    The adapter prevents accidental passing of obsolete optional
    arguments to a rebuilt engine while keeping the canonical view
    pipeline explicit.
    """

    try:
        return signature(function).parameters
    except (TypeError, ValueError):
        return {}


def _call_engine(function, **canonical_kwargs):
    """
    Call a rebuilt engine using only parameters present in its public
    signature.

    This is deliberately an integration safeguard, not an engineering
    compatibility hack. The canonical names used below match the
    current rebuilt architecture; unsupported optional parameters are
    simply not sent.
    """

    parameters = _accepted_parameters(function)

    if not parameters:
        return function(**canonical_kwargs)

    if any(
        parameter.kind == Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return function(**canonical_kwargs)

    accepted = {
        name
        for name, parameter in parameters.items()
        if parameter.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        )
    }

    kwargs = {
        key: value
        for key, value in canonical_kwargs.items()
        if key in accepted
    }

    missing_required = [
        name
        for name, parameter in parameters.items()
        if (
            parameter.default is Parameter.empty
            and parameter.kind in (
                Parameter.POSITIONAL_OR_KEYWORD,
                Parameter.KEYWORD_ONLY,
            )
            and name not in kwargs
        )
    ]

    if missing_required:
        raise TypeError(
            f"{function.__name__} requires unsupported/missing "
            f"parameters: {', '.join(missing_required)}"
        )

    return function(**kwargs)


# ---------------------------------------------------------------------
# LOAD INPUT
# ---------------------------------------------------------------------
def _build_loads_from_formset(formset) -> list[dict[str, Any]]:
    """
    Convert validated LoadItemFormSet rows into the canonical
    Load Engine input structure.
    """

    loads: list[dict[str, Any]] = []

    for form in formset:

        # Skip invalid forms
        if not form.is_valid():
            continue

        cleaned = form.cleaned_data

        # Skip empty forms
        if not cleaned:
            continue

        # Skip deleted forms
        if cleaned.get("DELETE"):
            continue

        appliance = cleaned.get("appliance")
        quantity = cleaned.get("quantity")
        hours_per_day = cleaned.get("hours_per_day")

        if quantity is None:
            continue

        if hours_per_day is None:
            continue

        # Appliance records provide defaults; custom entries are valid
        # engineering loads without being saved into the shared catalogue.
        if appliance is not None:
            name = appliance.name
            wattage = appliance.wattage
            surge_factor = appliance.surge_factor
            load_type = appliance.load_type
            starting_type = appliance.starting_type
        else:
            name = (cleaned.get("custom_name") or "").strip()
            wattage = cleaned.get("custom_wattage")
            surge_factor = Decimal("1")
            load_type = "resistive"
            starting_type = "single"

        if wattage is None:
            raise ValueError(
                f"{name or 'Custom appliance'}: wattage is required."
            )

        if surge_factor is None:
            surge_factor = Decimal("1")

        # ---------------------------------------------------------
        # CANONICAL LOAD ENGINE INPUT
        # ---------------------------------------------------------

        loads.append(
            {
                "name": name,

                "wattage": Decimal(
                    str(wattage)
                ),

                "quantity": int(
                    quantity
                ),

                "hours_per_day": Decimal(
                    str(hours_per_day)
                ),

                "surge_factor": Decimal(
                    str(surge_factor)
                ),

                "load_type": load_type,

                "starting_type": starting_type,
            }
        )

    return loads
def _build_loads_from_legacy_post(request: HttpRequest) -> list[dict[str, Any]]:
    """
    Transitional parser for the existing design.html.

    The current forms.py is authoritative, but this allows the view to
    survive the old array-based template until that template is rebuilt.
    """

    names = request.POST.getlist("appliance_name[]")
    quantities = request.POST.getlist("quantity[]")
    powers = request.POST.getlist("power[]")
    hours = request.POST.getlist("hours[]")
    surges = request.POST.getlist("surge[]")

    loads = []

    for index, name in enumerate(names):
        if not str(name).strip():
            continue

        try:
            quantity = int(quantities[index])
            watts = Decimal(powers[index])
            operating_hours = Decimal(hours[index])
        except (IndexError, TypeError, ValueError):
            continue

        try:
            surge = Decimal(surges[index])
        except (IndexError, TypeError, ValueError):
            surge = Decimal("1")

        if quantity <= 0 or watts <= 0 or operating_hours <= 0:
            continue

        loads.append(
            {
                "name": str(name).strip(),
                "watts": watts,
                "qty": quantity,
                "hours": operating_hours,
                "surge": surge if surge > 0 else Decimal("1"),
                "load_type": "resistive",
                "starting_type": "single",
            }
        )

    return loads


def _build_loads(request: HttpRequest, formset) -> list[dict[str, Any]]:
    """Prefer the rebuilt formset, then fall back to legacy posted rows."""

    loads = _build_loads_from_formset(formset)

    if loads:
        return loads

    return _build_loads_from_legacy_post(request)


# ---------------------------------------------------------------------
# DESIGN FORM NORMALIZATION
# ---------------------------------------------------------------------

def _normalized_design_post(request: HttpRequest):
    """
    Normalize names from the old design.html to the current forms.py
    without changing the form definitions.
    """

    data = request.POST.copy()

    if not data.get("client_name") and data.get("customer_name"):
        data["client_name"] = data.get("customer_name")

    if not data.get("autonomy_days") and data.get("backup_days"):
        data["autonomy_days"] = data.get("backup_days")

    return data


# ---------------------------------------------------------------------
# DESIGN CONTEXT
# ---------------------------------------------------------------------

def _design_context(
    *,
    design_form,
    requirements_form,
    battery_form,
    load_formset,
    request=None,
):
    return {
        "form": design_form,
        "design_form": design_form,
        "requirements_form": requirements_form,
        "battery_form": battery_form,
        "load_formset": load_formset,
        
                "panels": sorted(
            product_bridge.get_active_panels(),
            key=lambda p: (p.brand, p.model),
        ),
        "inverters": sorted(
            product_bridge.get_active_inverters(),
            key=lambda i: (i.brand, i.model),
        ),
        "controllers": sorted(
            product_bridge.get_active_controllers(),
            key=lambda c: (c.brand, c.model),
        ),
        "appliances": Appliance.objects.filter(
            wattage__gt=0
        ).order_by(
            "category",
            "name",
        ),
    }


# ---------------------------------------------------------------------
# COMPLETE DESIGN PIPELINE
# ---------------------------------------------------------------------

def run_design_pipeline(
    *,
    loads: list[dict[str, Any]],
    operating_mode: str,
    peak_sun_hours: Any,
    autonomy_days: Any = Decimal("1"),
    battery_type_preference: Any = None,
    require_hybrid_battery: bool = False,
    installation_type: str = "residential",
    offer_solar_generator: bool = False,
    project_location: str = "",
    settings: DesignSetting | None = None,
) -> Dict[str, Any]:
    """
    Run the rebuilt engineering pipeline in strict phase order.

    No manual product selection occurs here.
    """

    if not loads:
        raise ValueError("At least one valid electrical load is required.")

    settings = settings or DesignSetting.objects.first()

    if settings is None:
        raise ValueError(
            "Design settings have not been configured. "
            "Create at least one DesignSetting record first."
        )

    # ---------------------------------------------------------------
    # PHASE 1 — LOAD
    # ---------------------------------------------------------------

    load_result = calculate_load(loads) 
    _engine_success(load_result, "Load Engine")

    # ---------------------------------------------------------------
    # PHASE 2 — SYSTEM VOLTAGE
    # ---------------------------------------------------------------

    voltage_result = determine_system_voltage(load_result)
    _engine_success(voltage_result, "System Voltage Engine")

    # Align system voltage with active catalogue capabilities for the requested mode and phase
    target_inverters = product_bridge.get_active_inverters()
    if operating_mode == "hybrid":
        hybrid_inverters = [candidate for candidate in target_inverters if candidate.hybrid]
        if hybrid_inverters:
            target_inverters = hybrid_inverters
    if installation_type == "industrial":
        three_phase = [candidate for candidate in target_inverters if getattr(candidate, "phase", "single_phase") == "three_phase"]
        if three_phase:
            target_inverters = three_phase
    else:
        single_phase = [candidate for candidate in target_inverters if getattr(candidate, "phase", "single_phase") == "single_phase"]
        if single_phase:
            target_inverters = single_phase

    if target_inverters:
        active_voltages = sorted(list(set(int(float(getattr(c, "dc_voltage", 0) or 0)) for c in target_inverters if float(getattr(c, "dc_voltage", 0) or 0) > 0)))
        if active_voltages:
            current_v = int(float(voltage_result.get("system_voltage", 0) or 0))
            if current_v not in active_voltages:
                valid_higher = [v for v in active_voltages if v >= current_v]
                target_v = min(valid_higher) if valid_higher else max(active_voltages)
                voltage_result["system_voltage"] = target_v
                voltage_result["selected_voltage"] = target_v
                voltage_result["recommended_system_voltage"] = target_v
                if isinstance(voltage_result.get("required"), dict):
                    voltage_result["required"]["system_voltage"] = target_v
                    voltage_result["required"]["nominal_system_voltage"] = target_v
                    voltage_result["required"]["minimum_system_voltage"] = target_v

    system_voltage = _system_voltage(voltage_result)

    # ---------------------------------------------------------------
    # PHASE 3 — BATTERY
    # ---------------------------------------------------------------



    battery_candidates = product_bridge.get_active_batteries()

    if battery_type_preference:
        battery_candidates = [
            candidate
            for candidate in battery_candidates
            if getattr(candidate, "battery_type", None)
            == battery_type_preference
        ]

    if require_hybrid_battery:
        battery_candidates = [
            candidate for candidate in battery_candidates
            if getattr(candidate, "hybrid_compatible", False)
        ]

    battery_result = _call_engine(
        calculate_battery_system,
        load_result=load_result,
        voltage_result=voltage_result,
        battery_candidates=battery_candidates,
        autonomy_days=autonomy_days,
    )

    battery_result.setdefault("required", {})["battery_type"] = (
        battery_type_preference or "Any compatible type"
    )

    _engine_success(
        battery_result,
        "Battery Engine",
        allow_catalogue_gap=True,
    )


    # ---------------------------------------------------------------
# PHASE 4 — PV ARRAY
# ---------------------------------------------------------------

    panel_result = _call_engine(
        calculate_pv_array,
        load_result=load_result,
        voltage_result=voltage_result,
        battery_result=battery_result,
        panel_candidates=product_bridge.get_active_panels(),
        peak_sun_hours=peak_sun_hours,
        performance_ratio=settings.performance_ratio,
        future_expansion_factor=settings.future_expansion,
    )
    _engine_success(
        panel_result,
        "PV / Solar Array Engine",
        allow_catalogue_gap=True,
    )
    # ---------------------------------------------------------------
    # PHASE 5 — INVERTER
    # ---------------------------------------------------------------

    inverter_candidates = product_bridge.get_active_inverters()
    # Prefer catalogue entries matching the requested operating mode and
    # phase, but retain the active catalogue if metadata is incomplete or
    # no exact match exists. Phase 5 evaluates electrical compatibility.
    if operating_mode == "hybrid":
        hybrid_candidates = [candidate for candidate in inverter_candidates if getattr(candidate, "hybrid", False)]
        if hybrid_candidates:
            inverter_candidates = hybrid_candidates
    requested_phase = "three_phase" if installation_type == "industrial" else "single_phase"
    phase_candidates = [candidate for candidate in inverter_candidates if getattr(candidate, "phase", "single_phase") == requested_phase]
    if phase_candidates:
        inverter_candidates = phase_candidates

    inverter_result = _call_engine(
        calculate_inverter,
        load_result=load_result,
        voltage_result=voltage_result,
        battery_result=battery_result,
        inverters=inverter_candidates,
        phase=requested_phase,
    )
    _engine_success(inverter_result, "Inverter Engine", allow_catalogue_gap=True)

    if offer_solar_generator:
        calculations = load_result.get("calculations", {})
        inverter_requirements = inverter_result.get("required", {}) if isinstance(inverter_result.get("required"), dict) else {}
        required_power = Decimal(str(inverter_requirements.get("minimum_rated_power_w", calculations.get("peak_design_load_w", 0)) or 0))
        required_surge = Decimal(str(inverter_requirements.get("minimum_surge_power_w", calculations.get("surge_peak_load_w", 0)) or 0))
        required_energy = Decimal(str(calculations.get("daily_energy_kwh", 0))) * Decimal(str(autonomy_days))
        phase = "three_phase" if installation_type == "industrial" else "single_phase"
        required_capacity = {
            "minimum_rated_power_w": required_power,
            "minimum_surge_power_w": required_surge,
            "minimum_battery_capacity_wh": required_energy * Decimal("1000"),
            "minimum_battery_capacity_kwh": required_energy,
            "battery_voltage": inverter_requirements.get("system_voltage", system_voltage),
            "phase": phase,
            "unit_quantity": 1,
        }
        compatible_generators = [
            generator for generator in product_bridge.get_active_solar_generators()
            if Decimal(str(generator.inverter_rated_power)) >= required_power
            and Decimal(str(generator.battery_capacity_kwh)) >= required_energy
            and getattr(generator, "phase", "single_phase") == phase
        ]
        if compatible_generators:
            generator = min(
                compatible_generators,
                key=lambda item: (Decimal(str(item.inverter_rated_power)), Decimal(str(item.price))),
            )
            generator_payload = {
                "product_id": generator.product_id,
                "name": generator.name,
                "brand": generator.brand,
                "model": generator.model,
                "price": generator.price,
                "battery_capacity_kwh": generator.battery_capacity_kwh,
                "inverter_rated_power": generator.inverter_rated_power,
                "rated_power_w": generator.inverter_rated_power,
                "inverter_surge_power": generator.inverter_surge_power,
                "surge_power_w": generator.inverter_surge_power,
                "battery_capacity_wh": Decimal(str(generator.battery_capacity_kwh)) * Decimal("1000"),
                "phase": generator.phase,
                "output_voltage": generator.output_voltage,
                "hybrid": generator.hybrid,
                "note": "Integrated solar generator selected; confirm PV input and runtime with the supplier.",
            }
            inverter_result["solar_generator_option"] = {
                "available": True,
                "preferred": True,
                "required_capacity": _json_safe(required_capacity),
                "selected_generator": generator_payload,
                **generator_payload,
            }
        else:
            inverter_result["solar_generator_option"] = {
                "available": False,
                "preferred": True,
                "required_capacity": _json_safe(required_capacity),
                "note": "No active catalogue solar generator meets this load, energy and phase requirement.",
            }


    # ---------------------------------------------------------------
    # PHASE 6 — CHARGE CONTROLLER
    # ---------------------------------------------------------------

    controller_result = _call_engine(
        calculate_charge_controller,
        system_voltage=system_voltage,
        panel_result=panel_result,
        voltage_result=voltage_result,
        battery_result=battery_result,
        controllers=product_bridge.get_active_controllers(),
    )
    _engine_success(controller_result, "Charge Controller Engine", allow_catalogue_gap=True)

    # ---------------------------------------------------------------
    # PHASE 7/8 — PROTECTION
    # ---------------------------------------------------------------

    protection_result = _call_engine(
        calculate_protection,
        system_voltage=system_voltage,
        battery_result=battery_result,
        panel_result=panel_result,
        inverter_result=inverter_result,
        operating_mode=operating_mode,
    )
    _engine_success(protection_result, "Protection Engine", allow_catalogue_gap=True)

    # ---------------------------------------------------------------
    # CABLES
    # ---------------------------------------------------------------

    cable_result = _call_engine(
        calculate_cables,
        load_analysis=load_result,
        battery_result=battery_result,
        panel_result=panel_result,
        controller_result=controller_result,
        inverter_result=inverter_result,
        protection_result=protection_result,
    )
    _engine_success(cable_result, "Cable Engine", allow_catalogue_gap=True)

    # ---------------------------------------------------------------
    # ACCESSORIES
    # ---------------------------------------------------------------

    accessory_result = _call_engine(
        calculate_accessories,
        battery_result=battery_result,
        panel_result=panel_result,
        controller_result=controller_result,
        inverter_result=inverter_result,
        protection_result=protection_result,
        cable_result=cable_result,
        operating_mode=operating_mode,
    )
    _engine_success(accessory_result, "Accessories Engine", allow_catalogue_gap=True)

    # ---------------------------------------------------------------
    # BOQ
    # ---------------------------------------------------------------

    boq_result = _call_engine(
        generate_boq,
        battery_result=battery_result,
        panel_result=panel_result,
        controller_result=controller_result,
        inverter_result=inverter_result,
        protection_result=protection_result,
        cable_result=cable_result,
        accessory_result=accessory_result,
    )
    _engine_success(boq_result, "BOQ Engine", allow_catalogue_gap=True)
    _apply_generator_only_boq(boq_result, inverter_result)
    # Price transport with the same live vendor-distance calculation as checkout.
    transport_item = _solar_transport_item(boq_result.get("items", []), project_location)
    if transport_item and isinstance(boq_result.get("items"), list):
        transport_item["line_number"] = len(boq_result["items"]) + 1
        boq_result["items"].append(transport_item)

    # Nigerian installer labour benchmark: ₦30,000 per kVA, with a
    # ₦100,000 minimum. A configured fixed installation price wins.
    inverter_selected = inverter_result.get("selected") or {}
    inverter_info = inverter_selected.get("inverter") or {}
    selected_generator = _selected_generator(inverter_result)
    if _generator_option(inverter_result) is not None:
        inverter_watts = (selected_generator or {}).get("inverter_rated_power", 0)
    else:
        inverter_watts = inverter_selected.get("rated_power") or inverter_info.get("rated_power") or 0
    inverter_kva = Decimal(str(inverter_watts)) / Decimal("1000")
    labour_allowance = max(Decimal("100000"), inverter_kva * Decimal("30000"))
    installation_price = (
        Decimal("0") if _generator_option(inverter_result) is not None and not selected_generator
        else settings.installation_price or labour_allowance
    )

    boq_result["settings"] = {
        "installation_percentage": settings.installation_percentage,
        "installation_price": installation_price,
        "profit_percentage": settings.profit_percentage,
        "vat_percentage": settings.vat_percentage,
    }

    # ---------------------------------------------------------------
    # PRICING
    # ---------------------------------------------------------------

    pricing_result = _call_engine(
        calculate_pricing,
        boq_result=boq_result,
    )
    _engine_success(pricing_result, "Pricing Engine", allow_catalogue_gap=True)

        # ---------------------------------------------------------------
    # PHASE 11 — WARNINGS
    # ---------------------------------------------------------------

    result = {
        "load_result": load_result,
        "voltage_result": voltage_result,
        "battery_result": battery_result,
        "panel_result": panel_result,
        "controller_result": controller_result,
        "inverter_result": inverter_result,
        "protection_result": protection_result,
        "cable_result": cable_result,
        "accessory_result": accessory_result,
        "boq_result": boq_result,
        "pricing_result": pricing_result,
        "design_inputs": {
            "operating_mode": operating_mode,
            "peak_sun_hours": peak_sun_hours,
            "autonomy_days": autonomy_days,
            "installation_type": installation_type,
            "solution_preference": "generator" if offer_solar_generator else "components",
        },
    }

    # ---------------------------------------------------------------
    # WARNING ENGINE
    # ---------------------------------------------------------------

    result["warnings_result"] = calculate_warnings(
        load_result=load_result,
        voltage_result=voltage_result,
        battery_result=battery_result,
        panel_result=panel_result,
        inverter_result=inverter_result,
        controller_result=controller_result,
        protection_result=protection_result,
        cable_result=cable_result,
        accessory_result=accessory_result,
        boq_result=boq_result,
        pricing_result=pricing_result,
    )

    return _json_safe(result)



# ---------------------------------------------------------------------
# CREATE DESIGN
# ---------------------------------------------------------------------

@transaction.atomic
def solar_design(request: HttpRequest) -> HttpResponse:
    """
    Main Solar PV Design Calculator.

    Workflow:

        Calculator POST
            ↓
        Validate project forms
            ↓
        Validate electrical-load formset
            ↓
        Build normalized loads
            ↓
        Run complete solar design pipeline
            ↓
        Persist SolarDesign
            ↓
        Redirect to result page
    """

    # ================================================================
    # GET
    # ================================================================

    if request.method == "GET":
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=SolarDesignForm(),
                requirements_form=DesignRequirementsForm(),
                battery_form=BatteryPreferenceForm(),
                load_formset=LoadItemFormSet(),
            ),
        )

    # ================================================================
    # POST
    # ================================================================

    # Do NOT reconstruct the POST manually here unless the
    # normalization function is known to preserve the formset
    # management-form keys and every load field.
    #
    # The Django forms should receive the original POST data.
    post_data = request.POST.copy()

    design_form = SolarDesignForm(
        post_data
    )

    requirements_form = DesignRequirementsForm(
        post_data
    )

    battery_form = BatteryPreferenceForm(
        post_data
    )

    load_formset = LoadItemFormSet(
        post_data
    )

    # ================================================================
    # VALIDATE ALL USER INPUT
    # ================================================================

    design_valid = design_form.is_valid()
    requirements_valid = requirements_form.is_valid()
    battery_valid = battery_form.is_valid()
    loads_valid = load_formset.is_valid()

    if not (
        design_valid
        and requirements_valid
        and battery_valid
        and loads_valid
    ):
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            ),
        )

    # ================================================================
    # BUILD ENGINE LOAD INPUT
    # ================================================================

    try:
        loads = _build_loads(
            request,
            load_formset,
        )

    except Exception as exc:
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            )
            | {
                "error": (
                    "Unable to process the electrical loads: "
                    f"{exc}"
                ),
            },
        )

    # ================================================================
    # REQUIRE AT LEAST ONE LOAD
    # ================================================================

    if not loads:
        load_formset._non_form_errors = (
            load_formset.error_class(
                [
                    "At least one valid electrical load "
                    "is required."
                ]
            )
        )

        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            ),
        )

    # ================================================================
    # EXTRACT CLEAN DATA
    # ================================================================

    design_data = design_form.cleaned_data
    mismatched = [row["name"] for row in loads if row.get("installation_type") and row["installation_type"] != design_data["installation_type"]]
    if mismatched:
        load_formset._non_form_errors = load_formset.error_class(["Select appliances that match the Project Type: " + ", ".join(mismatched)])
        return render(request, "solar/calculator.html", _design_context(design_form=design_form, requirements_form=requirements_form, battery_form=battery_form, load_formset=load_formset))
    requirement_data = requirements_form.cleaned_data

    # Battery preference is intentionally retained as part of the
    # calculator contract, but battery selection remains an engine
    # responsibility rather than a manual product-selection step.
    battery_data = battery_form.cleaned_data

    # ================================================================
    # RUN COMPLETE DESIGN PIPELINE
    # ================================================================

    try:
        design_result = run_design_pipeline(
            loads=loads,
            operating_mode=design_data[
                "operating_mode"
            ],
            peak_sun_hours=design_data[
                "peak_sun_hours"
            ],
            autonomy_days=requirement_data[
                "autonomy_days"
            ],
            battery_type_preference=battery_data["battery_type"],
            require_hybrid_battery=battery_data["require_hybrid_battery"],
            installation_type=design_data["installation_type"],
            offer_solar_generator=(battery_data["solution_preference"] == "generator"),
            project_location=design_data.get("project_location", ""),
        )

    except Exception as exc:
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            )
            | {
                "error": (
                    "The solar design calculation could not "
                    f"be completed: {exc}"
                ),
            },
        )

    # ================================================================
    # VERIFY PIPELINE RESULT
    # ================================================================

    required_results = (
        "load_result",
        "voltage_result",
        "battery_result",
        "panel_result",
        "controller_result",
        "inverter_result",
        "protection_result",
        "cable_result",
        "accessory_result",
        "boq_result",
        "pricing_result",
    )

    missing_results = [
        key
        for key in required_results
        if key not in design_result
    ]

    if missing_results:
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            )
            | {
                "error": (
                    "The design pipeline returned an incomplete "
                    "result. Missing stages: "
                    + ", ".join(missing_results)
                ),
            },
        )

    # ================================================================
    # CREATE DATABASE RECORD
    # ================================================================

    try:
        design = SolarDesign.objects.create(
            user=request.user if request.user.is_authenticated else None,

            project_name=design_data[
                "project_name"
            ],

            client_name=design_data.get(
                "client_name",
                "",
            ),

            project_location=design_data.get(
                "project_location",
                "",
            ),

            description=design_data.get(
                "description",
                "",
            ),

            operating_mode=design_data[
                "operating_mode"
            ],

            installation_type=design_data["installation_type"],

            peak_sun_hours=design_data[
                "peak_sun_hours"
            ],

            autonomy_days=requirement_data[
                "autonomy_days"
            ],

            load_result=design_result[
                "load_result"
            ],

            voltage_result=design_result[
                "voltage_result"
            ],

            battery_result=design_result[
                "battery_result"
            ],

            panel_result=design_result[
                "panel_result"
            ],

            controller_result=design_result[
                "controller_result"
            ],

            inverter_result=design_result[
                "inverter_result"
            ],

            protection_result=design_result[
                "protection_result"
            ],

            cable_result=design_result[
                "cable_result"
            ],

            accessory_result=design_result[
                "accessory_result"
            ],

            boq_result=design_result[
                "boq_result"
            ],

            pricing_result=design_result[
                "pricing_result"
            ],

            warnings_result=design_result[
                "warnings_result"
            ],

            status="designed",
        )

    except Exception as exc:
        return render(
            request,
            "solar/calculator.html",
            _design_context(
                design_form=design_form,
                requirements_form=requirements_form,
                battery_form=battery_form,
                load_formset=load_formset,
            )
            | {
                "error": (
                    "The solar design was calculated but could "
                    "not be saved: "
                    f"{exc}"
                ),
            },
        )

    # ================================================================
    # SUCCESS
    # ================================================================

    messages.success(
        request,
        (
            f"Solar design '{design.project_name}' "
            "completed successfully."
        ),
    )

    if not request.user.is_authenticated:
        ids = set(request.session.get("guest_solar_design_ids", []))
        ids.add(design.id)
        request.session["guest_solar_design_ids"] = list(ids)
    return redirect("design_result", design_id=design.id)
# ---------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------

def solar_design_result(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    designs = SolarDesign.objects.filter(id=design_id)
    if request.user.is_authenticated:
        designs = designs.filter(user=request.user)
    else:
        designs = designs.filter(user__isnull=True, id__in=request.session.get("guest_solar_design_ids", []))
    design = get_object_or_404(designs)

    # Rebuild display pricing from saved component selections. Older designs
    # may predate the BOQ support for nested prices and total_quantity.
    boq = design.boq_result if isinstance(design.boq_result, dict) else {}
    pricing = design.pricing_result if isinstance(design.pricing_result, dict) else {}
    try:
        refreshed_boq = generate_boq(
            battery_result=design.battery_result,
            panel_result=design.panel_result,
            controller_result=design.controller_result,
            inverter_result=design.inverter_result,
            protection_result=design.protection_result,
            cable_result=design.cable_result,
            accessory_result=design.accessory_result,
        )
        _apply_generator_only_boq(refreshed_boq, design.inverter_result)
        transport_item = _solar_transport_item(refreshed_boq.get("items", []), design.project_location)
        if transport_item:
            transport_item["line_number"] = len(refreshed_boq["items"]) + 1
            refreshed_boq["items"].append(transport_item)
        refreshed_boq["settings"] = boq.get("settings", {})
        if _generator_option(design.inverter_result) is not None and not _selected_generator(design.inverter_result):
            refreshed_boq["settings"]["installation_price"] = 0
        refreshed_boq["totals"]["line_count"] = len(refreshed_boq["items"])
        refreshed_boq["totals"]["total_price"] = sum(
            Decimal(str(item.get("total_price", 0) or 0))
            for item in refreshed_boq["items"]
        )
        boq = _json_safe(refreshed_boq)
        pricing = _json_safe(calculate_pricing(boq_result=refreshed_boq))
    except Exception:
        # Keep the saved response if catalogue refresh is unavailable.
        pass
    return render(
        request,
        "solar/design_result.html",
        {
            "design": design,
            "load": design.load_result,
            "system_voltage": design.voltage_result,
            "battery": design.battery_result,
            "panel": design.panel_result,
            "controller": design.controller_result,
            "inverter": design.inverter_result,
            "protection": design.protection_result,
            "cables": design.cable_result,
            "accessories": design.accessory_result,
            "boq": boq,
            "pricing": pricing,
            "warnings": design.warnings_result,
        },
    )



@require_POST
def solar_shipping_quote(request: HttpRequest, design_id: int) -> HttpResponse:
    """Update a saved solar design location and checkout-style delivery quote."""
    designs = SolarDesign.objects.filter(id=design_id)
    if request.user.is_authenticated:
        designs = designs.filter(user=request.user)
    else:
        designs = designs.filter(user__isnull=True, id__in=request.session.get("guest_solar_design_ids", []))
    design = get_object_or_404(designs)
    address = str(request.POST.get("address", "")).strip()
    if not address:
        return JsonResponse({"error": "Select or enter a delivery address."}, status=400)

    try:
        refreshed_boq = generate_boq(
            battery_result=design.battery_result,
            panel_result=design.panel_result,
            controller_result=design.controller_result,
            inverter_result=design.inverter_result,
            protection_result=design.protection_result,
            cable_result=design.cable_result,
            accessory_result=design.accessory_result,
        )
        _apply_generator_only_boq(refreshed_boq, design.inverter_result)
        transport_item = _solar_transport_item(refreshed_boq.get("items", []), address)
        if not transport_item:
            return JsonResponse({"error": "Choose a supported city or state so delivery distance can be calculated."}, status=400)
        transport_item["line_number"] = len(refreshed_boq["items"]) + 1
        refreshed_boq["items"].append(transport_item)

        saved_boq = design.boq_result if isinstance(design.boq_result, dict) else {}
        settings_data = dict(saved_boq.get("settings", {}))
        option = _generator_option(design.inverter_result)
        generator = _selected_generator(design.inverter_result)
        if option is not None and not generator:
            settings_data["installation_price"] = 0
        elif option is not None and not settings_data.get("installation_price"):
            watts = Decimal(str(generator.get("inverter_rated_power", 0) or 0))
            settings_data["installation_price"] = float(max(Decimal("100000"), watts / Decimal("1000") * Decimal("30000")))
        refreshed_boq["settings"] = settings_data
        refreshed_boq["totals"]["line_count"] = len(refreshed_boq["items"])
        refreshed_boq["totals"]["total_price"] = sum(
            (Decimal(str(item.get("total_price", 0) or 0)) for item in refreshed_boq["items"]),
            Decimal("0"),
        )
        pricing = calculate_pricing(boq_result=refreshed_boq)
        design.project_location = address
        design.boq_result = _json_safe(refreshed_boq)
        design.pricing_result = _json_safe(pricing)
        design.save(update_fields=["project_location", "boq_result", "pricing_result", "updated_at"])
        return JsonResponse({
            "address": address,
            "transport_cost": float(transport_item["total_price"]),
            "boq": design.boq_result,
            "pricing": design.pricing_result,
        })
    except Exception:
        return JsonResponse({"error": "The delivery quote could not be updated. Please try again."}, status=500)

# ---------------------------------------------------------------------
# HISTORY / DASHBOARD
# ---------------------------------------------------------------------

@login_required
def solar_design_history(request: HttpRequest) -> HttpResponse:
    designs = SolarDesign.objects.filter(
        user=request.user,
    ).order_by("-created_at")

    return render(
        request,
        "solar/design_history.html",
        {"designs": designs},
    )


@login_required
def solar_dashboard(request: HttpRequest) -> HttpResponse:
    designs = SolarDesign.objects.filter(
        user=request.user,
        archived=False,
    )

    total_projects = designs.count()

    total_capacity = sum(
        Decimal(str(
            design.panel_result
            .get("selected", {})
            .get("array_power", 0)
        ))
        for design in designs
        if design.panel_result
    )

    total_value = sum(
        Decimal(str(
            design.pricing_result.get("grand_total", 0)
        ))
        for design in designs
        if design.pricing_result
    )

    return render(
        request,
        "solar/dashboard.html",
        {
            "designs": designs,
            "total_projects": total_projects,
            "total_capacity": total_capacity,
            "total_value": total_value,
        },
    )


# ---------------------------------------------------------------------
# PROJECT OPERATIONS
# ---------------------------------------------------------------------

@login_required
def project_details(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    return render(
        request,
        "solar/project_details.html",
        {"design": design},
    )


@login_required
def favorite_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    design.favorite = not design.favorite
    design.save(update_fields=["favorite", "updated_at"])

    return redirect(
        "solar_design_result",
        design_id=design.id,
    )


@login_required
def delete_solar_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    if request.method == "POST":
        project_name = design.project_name
        design.delete()

        messages.success(
            request,
            f"Design '{project_name}' deleted successfully.",
        )

        return redirect("solar_design_history")

    return render(
        request,
        "solar/project_confirm_delete.html",
        {"design": design},
    )


@login_required
def duplicate_solar_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    original = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    duplicate = SolarDesign.objects.create(
        user=request.user,
        project_name=f"{original.project_name} Copy",
        client_name=original.client_name,
        project_location=original.project_location,
        description=original.description,
        operating_mode=original.operating_mode,
        peak_sun_hours=original.peak_sun_hours,
        autonomy_days=original.autonomy_days,
        load_result=original.load_result,
        voltage_result=original.voltage_result,
        battery_result=original.battery_result,
        panel_result=original.panel_result,
        controller_result=original.controller_result,
        inverter_result=original.inverter_result,
        protection_result=original.protection_result,
        cable_result=original.cable_result,
        accessory_result=original.accessory_result,
        boq_result=original.boq_result,
        pricing_result=original.pricing_result,
        warnings_result=original.warnings_result,
        status="designed",
    )

    messages.success(
        request,
        "Solar design duplicated successfully.",
    )

    return redirect(
        "solar_design_result",
        design_id=duplicate.id,
    )


# ---------------------------------------------------------------------
# ARCHIVE
# ---------------------------------------------------------------------

@login_required
def archive_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    if request.method == "POST":
        design.archived = True
        design.save(update_fields=["archived", "updated_at"])

        messages.success(
            request,
            "Design archived successfully.",
        )

    return redirect(
        "solar_design_result",
        design_id=design.id,
    )


@login_required
def restore_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    design.archived = False
    design.save(update_fields=["archived", "updated_at"])

    messages.success(
        request,
        "Design restored successfully.",
    )

    return redirect(
        "solar_design_result",
        design_id=design.id,
    )


@login_required
def archived_projects(request: HttpRequest) -> HttpResponse:
    projects = SolarDesign.objects.filter(
        user=request.user,
        archived=True,
    ).order_by("-created_at")

    return render(
        request,
        "solar/archived_projects.html",
        {"projects": projects},
    )


# ---------------------------------------------------------------------
# VERSIONING
# ---------------------------------------------------------------------

@login_required
def project_versions(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    versions = SolarDesignVersion.objects.filter(
        design=design,
    ).order_by("-version")

    return render(
        request,
        "solar/project_versions.html",
        {
            "design": design,
            "versions": versions,
        },
    )


@login_required
@transaction.atomic
def save_project_version(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    latest = (
        SolarDesignVersion.objects
        .filter(design=design)
        .order_by("-version")
        .first()
    )

    version_number = (
        latest.version + 1
        if latest
        else 1
    )

    SolarDesignVersion.objects.create(
        design=design,
        version=version_number,
        created_by=request.user,
        load_result=design.load_result,
        voltage_result=design.voltage_result,
        battery_result=design.battery_result,
        panel_result=design.panel_result,
        controller_result=design.controller_result,
        inverter_result=design.inverter_result,
        protection_result=design.protection_result,
        cable_result=design.cable_result,
        accessory_result=design.accessory_result,
        boq_result=design.boq_result,
        pricing_result=design.pricing_result,
        warnings_result=design.warnings_result,
    )

    messages.success(
        request,
        f"Version {version_number} saved successfully.",
    )

    return redirect(
        "project_versions",
        design_id=design.id,
    )


@login_required
@transaction.atomic
def restore_project_version(
    request: HttpRequest,
    version_id: int,
) -> HttpResponse:
    version = get_object_or_404(
        SolarDesignVersion,
    EarthingDesign,
    ServiceRequest,
        id=version_id,
        design__user=request.user,
    )

    design = version.design

    for field in ENGINE_KEYS:
        setattr(
            design,
            field,
            getattr(version, field),
        )

    design.status = "designed"
    design.save()

    messages.success(
        request,
        f"Version {version.version} restored successfully.",
    )

    return redirect(
        "solar_design_result",
        design_id=design.id,
    )


# ---------------------------------------------------------------------
# UPDATE / RE-RUN
# ---------------------------------------------------------------------

@login_required
@transaction.atomic
def update_solar_design(
    request: HttpRequest,
    design_id: int,
) -> HttpResponse:
    design = get_object_or_404(
        SolarDesign,
        id=design_id,
        user=request.user,
    )

    if request.method != "POST":
        return render(
            request,
            "solar/update_design.html",
            {
                "design": design,
                "form": SolarDesignForm(instance=design),
                "requirements_form": DesignRequirementsForm(
                    initial={
                        "autonomy_days": design.autonomy_days,
                    }
                ),
                "battery_form": BatteryPreferenceForm(),
                "load_formset": LoadItemFormSet(),
            },
        )

    normalized_post = _normalized_design_post(request)

    design_form = SolarDesignForm(
        normalized_post,
        instance=design,
    )
    requirements_form = DesignRequirementsForm(normalized_post)
    battery_form = BatteryPreferenceForm(normalized_post)
    load_formset = LoadItemFormSet(normalized_post)

    if not (
        design_form.is_valid()
        and requirements_form.is_valid()
        and battery_form.is_valid()
        and load_formset.is_valid()
    ):
        return render(
            request,
            "solar/update_design.html",
            {
                "design": design,
                "form": design_form,
                "design_form": design_form,
                "requirements_form": requirements_form,
                "battery_form": battery_form,
                "load_formset": load_formset,
            },
        )

    loads = _build_loads(request, load_formset)

    if not loads:
        messages.error(
            request,
            "At least one valid electrical load is required.",
        )
        return redirect(
            "update_solar_design",
            design_id=design.id,
        )

    try:
        design_data = design_form.cleaned_data
        requirement_data = requirements_form.cleaned_data
        battery_data = battery_form.cleaned_data

        results = run_design_pipeline(
            loads=loads,
            operating_mode=design_data["operating_mode"],
            peak_sun_hours=design_data["peak_sun_hours"],
            autonomy_days=requirement_data["autonomy_days"],
            battery_type_preference=battery_data["battery_type"],
            require_hybrid_battery=battery_data["require_hybrid_battery"],
            installation_type=design_data["installation_type"],
            offer_solar_generator=(battery_data["solution_preference"] == "generator"),
            project_location=design_data.get("project_location", ""),
        )

        for field in ENGINE_KEYS:
            setattr(
                design,
                field,
                results[field],
            )

        design.project_name = design_data["project_name"]
        design.client_name = design_data.get("client_name", "")
        design.project_location = design_data.get("project_location", "")
        design.description = design_data.get("description", "")
        design.operating_mode = design_data["operating_mode"]
        design.installation_type = design_data["installation_type"]
        design.peak_sun_hours = design_data["peak_sun_hours"]
        design.autonomy_days = requirement_data["autonomy_days"]
        design.status = "designed"

        design.save()

        messages.success(
            request,
            "Solar design updated successfully.",
        )

        return redirect(
            "solar_design_result",
            design_id=design.id,
        )

    except Exception as exc:
        messages.error(
            request,
            f"Design update failed: {exc}",
        )

        return render(
            request,
            "solar/update_design.html",
            {
                "design": design,
                "form": design_form,
                "design_form": design_form,
                "requirements_form": requirements_form,
                "battery_form": battery_form,
                "load_formset": load_formset,
                "error": str(exc),
            },
        )


@login_required
def request_maintenance(request: HttpRequest, design_id: int) -> HttpResponse:
    design = get_object_or_404(SolarDesign, id=design_id, user=request.user)
    if request.method == "POST":
        ServiceRequest.objects.create(
            design=design,
            customer=request.user,
            subject=request.POST.get("subject") or f"Maintenance request — {design.project_name}",
            description=request.POST.get("description", ""),
            priority=request.POST.get("priority", "normal"),
        )
        messages.success(request, "Your maintenance request has been sent to the REMAROBE service team.")
        return redirect("design_result", design_id=design.id)
    return render(request, "solar/maintenance_request.html", {"design": design})

def earthing_assessment(request: HttpRequest):
    """Standalone or solar-linked preliminary earthing design and catalogue BOQ."""
    solar_design_id = request.GET.get("solar_design") or request.POST.get("solar_design")
    linked_design = None
    if solar_design_id and request.user.is_authenticated:
        linked_design = SolarDesign.objects.filter(id=solar_design_id, user=request.user).first()
    defaults = {"project_name": "", "client_name": "", "client_email": getattr(request.user, "email", ""), "project_location": "", "installation_type": "solar_pv", "ac_voltage": "400", "dc_voltage": "", "inverter_power": "", "pv_power": ""}
    if linked_design:
        inverter = ((linked_design.inverter_result or {}).get("selected") or {})
        panel = ((linked_design.panel_result or {}).get("selected") or {})
        defaults.update({
            "project_name": linked_design.project_name,
            "client_name": linked_design.client_name or getattr(request.user, "get_full_name", lambda: "")(),
            "project_location": linked_design.project_location,
            "installation_type": "solar_pv",
            "ac_voltage": str(inverter.get("output_voltage", 230)),
            "inverter_power": str(inverter.get("rated_power", inverter.get("power", ""))),
            "pv_power": str(panel.get("array_power", panel.get("power", ""))),
        })
    values = defaults.copy()
    result = None
    if request.method == "POST":
        values.update({key: value for key, value in request.POST.items()})
        result = calculate_earthing_design(values)
        keywords = ("earth rod", "earthing rod", "earth clamp", "earth pit", "inspection chamber", "copper tape", "copper strip", "earth cable", "bentonite", "ground enhancement", "test link", "earthing")
        catalogue = []
        for term in keywords:
            listing = ProductListing.objects.filter(is_active=True).filter(Q(name__icontains=term) | Q(categories__name__icontains=term)).distinct().first()
            if listing and listing not in catalogue:
                catalogue.append(listing)
        quantities = [result["rod_count"], result["ring_conductor_m"], result["rod_count"], result["rod_count"], result["enhancement_kg"]]
        result["boq"] = [{"product": product, "quantity": quantities[min(index, len(quantities)-1)], "unit": "m" if index == 1 else ("kg" if index == 4 else "pcs")} for index, product in enumerate(catalogue)]
        if request.user.is_authenticated:
            EarthingDesign.objects.create(user=request.user, solar_design=linked_design, project_name=values.get("project_name") or "Earthing Design", installation_type=values.get("installation_type", "industrial"), standard=values.get("standard", ""), inputs=_json_safe(values), result=_json_safe({key: value for key, value in result.items() if key != "boq"}))
    return render(request, "solar/earthing_assessment.html", {"result": result, "values": values, "solar_design_id": solar_design_id, "linked_design": linked_design})