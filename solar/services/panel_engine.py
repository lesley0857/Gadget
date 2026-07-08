# solar/services/panel_engine.py

import math


###############################################################
# TARGET ARRAY VOLTAGE
###############################################################

def determine_array_voltage(battery_voltage):
    """
    Recommended MPPT array voltage.

        12V -> 36V
        24V -> 72V
        48V -> 144V
        96V -> 288V
    """

    if battery_voltage <= 12:
        return 36

    if battery_voltage <= 24:
        return 72

    if battery_voltage <= 48:
        return 144

    return battery_voltage * 3


###############################################################
# PANEL SIZING ENGINE
###############################################################

def calculate_panels(
    daily_energy,
    peak_sun_hours,
    performance_ratio,
    panel,
    battery_voltage,
    oversize_factor=1.20,
):
    """
    Solar PV sizing engine.

    Returns

    {
        success,
        required,
        selected,
        closest,
        message,
        warnings
    }
    """

    warnings = []

    ###########################################################
    # VALIDATION
    ###########################################################

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

    if peak_sun_hours <= 0:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": "Peak Sun Hours must be greater than zero.",

            "warnings": [
                "Invalid Peak Sun Hours."
            ],
        }

    ###########################################################
    # REQUIRED PV POWER
    ###########################################################

    required_pv = (

        daily_energy
        *
        oversize_factor

        /

        (
            peak_sun_hours
            *
            performance_ratio
        )

    )

    ###########################################################
    # MINIMUM NUMBER OF PANELS
    ###########################################################

    minimum_panels = max(

        1,

        math.ceil(

            required_pv

            /

            panel.power

        )

    )

    ###########################################################
    # TARGET ARRAY VOLTAGE
    ###########################################################

    target_voltage = determine_array_voltage(
        battery_voltage
    )

    ###########################################################
    # SERIES PANELS
    ###########################################################

    series = max(

        1,

        math.ceil(

            target_voltage

            /

            panel.vmp

        )

    )

    ###########################################################
    # PARALLEL STRINGS
    ###########################################################

    parallel = max(

        1,

        math.ceil(

            minimum_panels

            /

            series

        )

    )

    ###########################################################
    # TOTAL PANELS
    ###########################################################

    quantity = series * parallel

    ###########################################################
    # ARRAY PARAMETERS
    ###########################################################

    array_voltage = panel.vmp * series

    array_voc = panel.voc * series

    corrected_voc = array_voc * 1.10

    array_current = panel.imp * parallel

    array_isc = panel.isc * parallel

    ###########################################################
    # INSTALLED POWER
    ###########################################################

    installed_power = quantity * panel.power

    ###########################################################
    # DAILY GENERATION
    ###########################################################

    daily_generation = (

        installed_power
        *
        peak_sun_hours
        *
        performance_ratio

    )

    ###########################################################
    # UTILIZATION
    ###########################################################

    utilization = (

        required_pv

        /

        installed_power

    ) * 100

    ###########################################################
    # WARNINGS
    ###########################################################

    if utilization > 95:

        warnings.append(

            "Solar array is operating close to its design limit."

        )

    if corrected_voc > 450:

        warnings.append(

            "High corrected open-circuit voltage."

        )

    ###########################################################
    # RETURN
    ###########################################################

    return {

        #######################################################
        # STATUS
        #######################################################

        "success": True,

        #######################################################
        # REQUIRED DESIGN
        #######################################################

        "required": {

            "pv_power":

                round(
                    required_pv,
                    2
                ),

            "target_voltage":

                target_voltage,
            "corrected_voc":

                round(
                    corrected_voc,
                    2
                ),
            "quantity":quantity,    
            "daily_energy":round(
                    daily_energy,
                    2
                ),
            "array_isc":

                round(
                    array_isc,
                    2
                ),
            "array_voltage":round(array_voltage,2),
            "array_current":round(array_current,2),
            "installed_power": round(installed_power,2)
        },

        #######################################################
        # SELECTED ARRAY
        #######################################################

        "selected": {

            "object":

                panel,

            "name":

                str(panel),

            "manufacturer":

                panel.brand,

            "power":

                panel.power,

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

        #######################################################
        # CLOSEST
        #######################################################

        "closest": None,

        #######################################################
        # MESSAGE
        #######################################################

        "message": None,

        #######################################################
        # WARNINGS
        #######################################################

        "warnings": warnings,
    }


