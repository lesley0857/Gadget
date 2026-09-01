"""Auditable preliminary earthing design calculations.

The module deliberately reports data gaps instead of claiming IEEE/IEC compliance.
"""
from decimal import Decimal, ROUND_UP
from math import log, pi, sqrt

D = Decimal


def _d(value, default=0):
    try:
        return D(str(value if value not in (None, "") else default))
    except Exception:
        return D(str(default))


def vertical_rod_resistance(resistivity, rod_length, diameter):
    """Approximate resistance of one vertical rod: rho/(2*pi*L)*(ln(4L/d)-1)."""
    rho, length, dia = _d(resistivity), _d(rod_length), _d(diameter)
    if rho <= 0 or length <= 0 or dia <= 0:
        return None
    return D(str(float(rho) / (2 * pi * float(length)) * (log((4 * float(length)) / float(dia)) - 1)))


def conductor_area(fault_current_ka, clearing_time_s, material):
    """Simplified adiabatic selection A=I*sqrt(t)/k; k must be project-verified."""
    current, time = _d(fault_current_ka) * D("1000"), _d(clearing_time_s)
    if current <= 0 or time <= 0:
        return None
    k = D("143") if material == "copper" else D("80")
    return current * D(str(sqrt(float(time)))) / k


def design(inputs):
    rho = _d(inputs.get("soil_resistivity"))
    target = _d(inputs.get("target_resistance"), 5)
    length = _d(inputs.get("rod_length"), 3)
    diameter = _d(inputs.get("rod_diameter"), D("0.016"))
    area = _d(inputs.get("available_area"), 100)
    mode = inputs.get("design_mode", "automatic")
    soil_known = rho > 0
    if not soil_known:
        defaults = {"wet_clay": 30, "clay": 50, "loam": 100, "laterite": 150, "sand": 500, "rocky": 1000}
        rho = D(str(defaults.get(inputs.get("soil_type"), 100)))
    single = vertical_rod_resistance(rho, length, diameter)
    spacing = max(length, D("3"))
    # Conservative mutual-interference factor grows with array size.
    rods = int(inputs.get("manual_rods") or 0) if mode == "manual" else 0
    if not rods:
        rods = 2
        while rods < 30:
            interference = D("1") + D("0.08") * D(str(rods - 1))
            expected = single * interference / D(str(rods))
            if expected <= target:
                break
            rods += 1
    interference = D("1") + D("0.08") * D(str(rods - 1))
    expected = single * interference / D(str(rods))
    footprint = spacing * D(str(max(rods - 1, 1)))
    grid_needed = rods >= 6 or inputs.get("installation_type") in {"industrial", "substation", "oil_gas"}
    method = "Multiple interconnected vertical electrodes with a ring conductor" if grid_needed else "Interconnected vertical earth electrodes"
    conductor = conductor_area(inputs.get("fault_current_ka"), inputs.get("clearing_time_s"), inputs.get("conductor_material", "copper"))
    warnings = []
    if not soil_known:
        warnings.append(("DATA REQUIRED", "Soil resistivity was not field measured. A provisional soil classification value was used; perform a Wenner or Schlumberger survey."))
    if footprint * spacing > area:
        warnings.append(("WARNING", "The estimated electrode footprint exceeds the stated available area. Use a ring/grid arrangement, deeper electrodes, or reassess the layout."))
    if conductor is None:
        warnings.append(("DATA REQUIRED", "Fault current and clearing time are required to validate conductor thermal withstand using an adiabatic method."))
    if inputs.get("lightning_protection") == "yes":
        warnings.append(("DATA REQUIRED", "Lightning protection selected: verify separation distance, down-conductor routing, bonding and SPD coordination separately."))
    if inputs.get("traditional_backfill") == "salt":
        warnings.append(("WARNING", "Salt is not automatically recommended because it can accelerate corrosion and contaminate soil. Use an approved enhancement material where appropriate."))
    enhancement_kg = (D(str(rods)) * length * D("12")).quantize(D("1"), rounding=ROUND_UP) if rho >= 150 else D("0")
    result = {
        "design_basis": "Preliminary resistance and quantity assessment; not an IEEE 80 touch/step-voltage study.",
        "method": method, "soil_resistivity_ohm_m": rho, "target_resistance_ohm": target,
        "single_rod_resistance_ohm": single.quantize(D("0.01")), "rod_count": rods,
        "rod_length_m": length, "rod_diameter_m": diameter, "spacing_m": spacing,
        "expected_resistance_ohm": expected.quantize(D("0.01")), "safety_margin_ohm": (target - expected).quantize(D("0.01")),
        "footprint_m": footprint, "ring_conductor_m": (footprint * 2 + D("10")).quantize(D("1")),
        "trench_depth_m": D("0.6"), "trench_width_m": D("0.3"),
        "enhancement_kg": enhancement_kg, "conductor_min_mm2": conductor.quantize(D("0.1")) if conductor else None,
        "warnings": warnings,
        "touch_step_status": "INSUFFICIENT DATA FOR VALID CALCULATION — requires fault current, clearing time, surface layer and grid geometry.",
        "formula": "Rrod = ρ/(2πL) × [ln(4L/d) − 1]; multi-rod result includes a conservative mutual-interference factor.",
    }
    return result