# solar/services/visualizer_service.py
"""
Builds the dynamic 3D visualizer equipment payload from a SolarDesign instance
and its underlying engineering results.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict, Optional

from solar.models import Product3DModel, SolarDesign


def _to_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _lookup_3d_asset(product_id: Optional[int], category_hint: str = "") -> Dict[str, Any]:
    """
    Look up Product3DModel for the given product ID, returning asset metadata.
    If no record exists or no model file is attached, returns placeholder info.
    """
    if not product_id:
        return {
            "has_exact_model": False,
            "status": "placeholder",
            "status_label": "Procedural 3D Model",
            "asset_url": "",
            "width_m": None,
            "height_m": None,
            "depth_m": None,
            "scale_factor": 1.0,
            "rotation_offset_y": 0.0,
        }

    try:
        m3d = Product3DModel.objects.filter(product_id=product_id).first()
        if m3d:
            asset_url = m3d.get_asset_url()
            is_verified = (m3d.status == "verified" and bool(asset_url))
            return {
                "has_exact_model": is_verified,
                "status": m3d.status,
                "status_label": m3d.get_status_display(),
                "asset_url": asset_url,
                "width_m": _to_float(m3d.width_m) if m3d.width_m else None,
                "height_m": _to_float(m3d.height_m) if m3d.height_m else None,
                "depth_m": _to_float(m3d.depth_m) if m3d.depth_m else None,
                "scale_factor": _to_float(m3d.scale_factor, 1.0),
                "rotation_offset_y": _to_float(m3d.rotation_offset_y, 0.0),
            }
    except Exception:
        pass

    return {
        "has_exact_model": False,
        "status": "placeholder",
        "status_label": "Procedural 3D Model",
        "asset_url": "",
        "width_m": None,
        "height_m": None,
        "depth_m": None,
        "scale_factor": 1.0,
        "rotation_offset_y": 0.0,
    }


def build_visualizer_data(design: SolarDesign) -> Dict[str, Any]:
    """
    Build the complete JSON-safe data structure for the 3D equipment visualizer.
    This reflects the exact equipment selected and quantities calculated.
    """
    panel_res = design.panel_result if isinstance(design.panel_result, dict) else {}
    inverter_res = design.inverter_result if isinstance(design.inverter_result, dict) else {}
    battery_res = design.battery_result if isinstance(design.battery_result, dict) else {}
    controller_res = design.controller_result if isinstance(design.controller_result, dict) else {}
    load_res = design.load_result if isinstance(design.load_result, dict) else {}
    voltage_res = design.voltage_result if isinstance(design.voltage_result, dict) else {}

    panel_sel = panel_res.get("selected") or {}
    inverter_sel = inverter_res.get("selected") or {}
    battery_sel = battery_res.get("selected") or {}
    controller_sel = controller_res.get("selected") or {}

    # === 1. SOLAR PANELS ===
    panel_info = panel_sel.get("panel") or {}
    panel_qty = _to_int(panel_sel.get("total_quantity"), 0)
    if panel_qty <= 0:
        s_count = _to_int(panel_sel.get("series_count"), 0)
        p_count = _to_int(panel_sel.get("parallel_count"), 0)
        panel_qty = s_count * p_count if (s_count and p_count) else 0

    panel_id = panel_info.get("id") or panel_sel.get("panel_id")
    panel_power = _to_float(panel_info.get("power"), 0.0)
    panel_brand = panel_info.get("brand") or ""
    panel_model = panel_info.get("model") or ""
    panel_name = f"{panel_brand} {panel_model}".strip() or "Solar Panel"
    total_panel_kw = _to_float(panel_sel.get("installed_power_kw"), 0.0)
    if total_panel_kw <= 0 and panel_power > 0 and panel_qty > 0:
        total_panel_kw = round((panel_power * panel_qty) / 1000.0, 2)

    panel_data = {
        "id": panel_id,
        "quantity": panel_qty,
        "name": panel_name,
        "brand": panel_brand,
        "model": panel_model,
        "rating": f"{int(panel_power)} W" if panel_power else "",
        "unit_power_w": panel_power,
        "total_power_kw": total_panel_kw,
        "series_count": _to_int(panel_sel.get("series_count"), 1),
        "parallel_count": _to_int(panel_sel.get("parallel_count"), 1),
        "asset": _lookup_3d_asset(panel_id, "panel"),
    }

    # === 2. BATTERIES ===
    bat_info = battery_sel.get("battery") or {}
    bat_qty = _to_int(battery_sel.get("total_quantity"), 0)
    if bat_qty <= 0:
        bs_count = _to_int(battery_sel.get("series_count"), 0)
        bp_count = _to_int(battery_sel.get("parallel_count"), 0)
        bat_qty = bs_count * bp_count if (bs_count and bp_count) else (1 if bat_info else 0)

    bat_id = bat_info.get("id") or battery_sel.get("battery_id")
    bat_brand = bat_info.get("brand") or ""
    bat_model = bat_info.get("model") or ""
    bat_name = bat_info.get("name") or f"{bat_brand} {bat_model}".strip() or "Battery Unit"
    bat_ah = _to_float(bat_info.get("capacity_ah"), 0.0)
    bat_v = _to_float(bat_info.get("voltage") or battery_sel.get("actual_bank_voltage"), 0.0)
    usable_kwh = _to_float(battery_sel.get("usable_energy_kwh"), 0.0)

    battery_data = {
        "id": bat_id,
        "quantity": bat_qty,
        "name": bat_name,
        "brand": bat_brand,
        "model": bat_model,
        "rating": f"{int(bat_ah)} Ah" if bat_ah else "",
        "voltage": bat_v,
        "capacity_ah": bat_ah,
        "usable_energy_kwh": usable_kwh,
        "series_count": _to_int(battery_sel.get("series_count"), 1),
        "parallel_count": _to_int(battery_sel.get("parallel_count"), 1),
        "asset": _lookup_3d_asset(bat_id, "battery"),
    }

    # === 3. INVERTER ===
    inv_qty = _to_int(inverter_sel.get("quantity") or inverter_sel.get("parallel_units"), 1)
    if not inverter_sel:
        inv_qty = 0

    inv_id = inverter_sel.get("id") or inverter_sel.get("product_id")
    inv_brand = inverter_sel.get("brand") or ""
    inv_model = inverter_sel.get("model") or ""
    inv_name = inverter_sel.get("name") or f"{inv_brand} {inv_model}".strip() or "Hybrid Inverter"
    inv_kw = _to_float(inverter_sel.get("rated_power_kw"), 0.0)
    inv_w = _to_float(inverter_sel.get("rated_power"), 0.0)
    if inv_kw <= 0 and inv_w > 0:
        inv_kw = round(inv_w / 1000.0, 1)

    inverter_data = {
        "id": inv_id,
        "quantity": inv_qty,
        "name": inv_name,
        "brand": inv_brand,
        "model": inv_model,
        "rating": f"{inv_kw:g} kVA" if inv_kw else (f"{int(inv_w)} W" if inv_w else ""),
        "rated_power_kw": inv_kw,
        "rated_power_w": inv_w,
        "dc_voltage": _to_float(inverter_sel.get("dc_voltage"), 48.0),
        "phase": inverter_sel.get("phase", "single_phase"),
        "hybrid": bool(inverter_sel.get("hybrid", True)),
        "asset": _lookup_3d_asset(inv_id, "inverter"),
    }

    # === 4. CHARGE CONTROLLER (if standalone) ===
    ctrl_qty = _to_int(controller_sel.get("quantity"), 0)
    controller_data = None
    if controller_sel and ctrl_qty > 0 and controller_sel.get("status") != "integrated":
        ctrl_id = controller_sel.get("id") or controller_sel.get("product_id")
        ctrl_brand = controller_sel.get("brand") or ""
        ctrl_model = controller_sel.get("model") or ""
        ctrl_name = controller_sel.get("name") or f"{ctrl_brand} {ctrl_model}".strip() or "MPPT Controller"
        ctrl_amps = _to_float(controller_sel.get("max_charge_current"), 0.0)

        controller_data = {
            "id": ctrl_id,
            "quantity": ctrl_qty,
            "name": ctrl_name,
            "brand": ctrl_brand,
            "model": ctrl_model,
            "rating": f"{int(ctrl_amps)} A" if ctrl_amps else "",
            "max_charge_current": ctrl_amps,
            "max_pv_voltage": _to_float(controller_sel.get("max_pv_voltage"), 0.0),
            "asset": _lookup_3d_asset(ctrl_id, "controller"),
        }

    # === 5. SYSTEM SUMMARY ===
    sys_voltage = _to_float(
        voltage_res.get("nominal_voltage") or battery_sel.get("system_voltage") or 48.0
    )
    daily_energy_kwh = _to_float(load_res.get("daily_energy_kwh"), 0.0)
    if daily_energy_kwh <= 0:
        daily_energy_kwh = round(_to_float(load_res.get("daily_energy_wh"), 0.0) / 1000.0, 2)

    # Solar generator detection
    is_solar_generator = False
    if "solar_generator_spec" in str(inverter_sel) or inverter_sel.get("is_generator"):
        is_solar_generator = True

    return {
        "design_id": design.id,
        "project_name": design.project_name or "Solar PV System",
        "client_name": design.client_name or "",
        "operating_mode": design.operating_mode or "hybrid",
        "is_solar_generator": is_solar_generator,
        "system_summary": {
            "system_voltage_v": sys_voltage,
            "total_panel_capacity_kw": total_panel_kw,
            "daily_energy_kwh": daily_energy_kwh,
            "inverter_rating_kva": inv_kw,
            "usable_storage_kwh": usable_kwh,
            "total_panels": panel_qty,
            "total_batteries": bat_qty,
            "total_inverters": inv_qty,
        },
        "equipment": {
            "panels": panel_data,
            "batteries": battery_data,
            "inverter": inverter_data,
            "controller": controller_data,
        },
    }

