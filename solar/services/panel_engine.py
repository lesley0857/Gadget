# solar/services/panel_engine.py

import math

def determine_array_voltage(
battery_voltage,
panel_vmp,
):

    battery_voltage = float(
        battery_voltage
    )

    panel_vmp = float(
        panel_vmp
    )

    if battery_voltage <= 0:

        raise ValueError(
            "Battery voltage must be greater than zero."
        )

    if panel_vmp <= 0:

        raise ValueError(
            "Panel Vmp must be greater than zero."
        )

    # Approximate minimum PV operating voltage
    # above the battery-system voltage.

    if battery_voltage <= 12:

        return 36

    if battery_voltage <= 24:

        return 72

    if battery_voltage <= 48:

        return 144

    return battery_voltage * 3


def calculate_panels(
daily_energy,
peak_sun_hours,
performance_ratio,
panel,
battery_voltage,
oversize_factor=1.20,
):
    """
    Calculate the PV array required for the selected
    battery-system voltage and daily energy demand.
    """

    warnings = []

    # ---------------------------------------------------------
    # VALIDATE PANEL
    # ---------------------------------------------------------

    if panel is None:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "closest": None,
            "message": "No solar panel selected.",
            "warnings": [
                "Panel selection is required."
            ],
        }

    # ---------------------------------------------------------
    # VALIDATE NUMERIC INPUTS
    # ---------------------------------------------------------

    try:

        daily_energy = float(
            daily_energy or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        daily_energy = 0

        warnings.append(
            "Invalid daily energy supplied. Zero was used."
        )

    if daily_energy < 0:

        daily_energy = 0

        warnings.append(
            "Daily energy cannot be negative."
        )

    try:

        peak_sun_hours = float(
            peak_sun_hours
        )

    except (
        TypeError,
        ValueError,
    ):

        peak_sun_hours = 0

    if peak_sun_hours <= 0:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "closest": None,
            "message": (
                "Peak Sun Hours must be greater than zero."
            ),
            "warnings": [
                "Invalid Peak Sun Hours."
            ],
        }

    try:

        performance_ratio = float(
            performance_ratio
        )

    except (
        TypeError,
        ValueError,
    ):

        performance_ratio = 0.80

        warnings.append(
            "Invalid performance ratio. 80% was used."
        )

    if performance_ratio > 1:

        performance_ratio /= 100

    if not 0 < performance_ratio <= 1:

        performance_ratio = 0.80

        warnings.append(
            "Invalid performance ratio. 80% was used."
        )

    try:

        oversize_factor = float(
            oversize_factor
        )

    except (
        TypeError,
        ValueError,
    ):

        oversize_factor = 1.20

        warnings.append(
            "Invalid PV oversize factor. 120% was used."
        )

    if oversize_factor < 1:

        oversize_factor = 1.0

        warnings.append(
            "PV oversize factor cannot be below 1.0."
        )

    try:

        battery_voltage = float(
            battery_voltage
        )

    except (
        TypeError,
        ValueError,
    ):

        battery_voltage = 0

    if battery_voltage <= 0:

        return {
            "success": False,
            "required": {},
            "selected": None,
            "closest": None,
            "message": (
                "Invalid battery-system voltage."
            ),
            "warnings": [
                "Battery voltage must be greater than zero."
            ],
        }

    # ---------------------------------------------------------
    # VALIDATE PANEL DATA
    # ---------------------------------------------------------

    try:

        panel_power = float(
            panel.power
        )

        panel_vmp = float(
            panel.vmp
        )

        panel_voc = float(
            panel.voc
        )

        panel_imp = float(
            panel.imp
        )

        panel_isc = float(
            panel.isc
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):

        return {
            "success": False,
            "required": {},
            "selected": None,
            "closest": None,
            "message": (
                "Selected panel has invalid electrical data."
            ),
            "warnings": [
                "Panel power, Vmp, Voc, Imp and Isc "
                "must be valid positive values."
            ],
        }

    if any(
        value <= 0
        for value in (
            panel_power,
            panel_vmp,
            panel_voc,
            panel_imp,
            panel_isc,
        )
    ):

        return {
            "success": False,
            "required": {},
            "selected": None,
            "closest": None,
            "message": (
                "Selected panel has invalid electrical data."
            ),
            "warnings": [
                "Panel electrical values must be greater than zero."
            ],
        }

    # ---------------------------------------------------------
    # TARGET PV VOLTAGE
    # ---------------------------------------------------------

    target_voltage = determine_array_voltage(
        battery_voltage,
        panel_vmp,
    )

    # ---------------------------------------------------------
    # PV ENERGY AND POWER REQUIREMENT
    # ---------------------------------------------------------

    required_pv_energy = (
        daily_energy
        /
        performance_ratio
    )

    required_pv_power = (
        required_pv_energy
        /
        peak_sun_hours
    )

    required_pv_power *= oversize_factor

    # ---------------------------------------------------------
    # PANEL CONFIGURATION
    # ---------------------------------------------------------

    minimum_panels = max(
        1,
        math.ceil(
            required_pv_power
            /
            panel_power
        ),
    )

    series = max(
        1,
        math.ceil(
            target_voltage
            /
            panel_vmp
        ),
    )

    parallel = max(
        1,
        math.ceil(
            minimum_panels
            /
            series
        ),
    )

    quantity = (
        series
        *
        parallel
    )

    # ---------------------------------------------------------
    # ARRAY ELECTRICAL VALUES
    # ---------------------------------------------------------

    array_voltage = (
        panel_vmp
        *
        series
    )

    array_voc = (
        panel_voc
        *
        series
    )

    corrected_voc = (
        array_voc
        *
        1.10
    )

    array_current = (
        panel_imp
        *
        parallel
    )

    array_isc = (
        panel_isc
        *
        parallel
    )

    installed_power = (
        quantity
        *
        panel_power
    )

    daily_generation = (
        installed_power
        *
        peak_sun_hours
        *
        performance_ratio
    )

    utilization = (

        required_pv_power
        /
        installed_power
        *
        100

    ) if installed_power > 0 else 0

    # ---------------------------------------------------------
    # WARNINGS
    # ---------------------------------------------------------

    if array_voltage < target_voltage:

        warnings.append(
            "PV array operating voltage is below "
            "the recommended target voltage."
        )

    if utilization > 95:

        warnings.append(
            "PV array is operating close to its "
            "calculated design requirement."
        )

    if utilization < 40:

        warnings.append(
            "Selected PV array provides a large "
            "design margin."
        )

    if corrected_voc > 450:

        warnings.append(
            "High corrected PV open-circuit voltage. "
            "Verify the charge-controller voltage rating."
        )

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------

    return {

        "success": True,

        "required": {

            "battery_voltage":
                round(
                    battery_voltage,
                    2
                ),

            "pv_energy":
                round(
                    required_pv_energy,
                    2
                ),

            "pv_power":
                round(
                    required_pv_power,
                    2
                ),

            "target_voltage":
                round(
                    target_voltage,
                    2
                ),

            "quantity":
                quantity,

            "array_voltage":
                round(
                    array_voltage,
                    2
                ),

            "array_voc":
                round(
                    array_voc,
                    2
                ),

            "corrected_voc":
                round(
                    corrected_voc,
                    2
                ),

            "array_current":
                round(
                    array_current,
                    2
                ),

            "array_isc":
                round(
                    array_isc,
                    2
                ),

            "installed_power":
                round(
                    installed_power,
                    2
                ),

        },

        "selected": {

            "object":
                panel,

            "name":
                str(
                    panel
                ),

            "manufacturer":
                panel.brand,

            "power":
                panel_power,

            "quantity":
                quantity,

            "series":
                series,

            "parallel":
                parallel,

            "installed_power":
                round(
                    installed_power,
                    2
                ),

            "array_voltage":
                round(
                    array_voltage,
                    2
                ),

            "array_voc":
                round(
                    array_voc,
                    2
                ),

            "corrected_voc":
                round(
                    corrected_voc,
                    2
                ),

            "array_current":
                round(
                    array_current,
                    2
                ),

            "array_isc":
                round(
                    array_isc,
                    2
                ),

            "daily_generation":
                round(
                    daily_generation,
                    2
                ),

            "utilization":
                round(
                    utilization,
                    2
                ),

            "peak_sun_hours":
                peak_sun_hours,

            "performance_ratio":
                performance_ratio,

            "oversize_factor":
                oversize_factor,

            "price":
                panel.price,

        },

        "closest":
            None,

        "message":
            None,

        "warnings":
            warnings,

    }

