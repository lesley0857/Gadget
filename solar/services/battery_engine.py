# solar/services/battery_engine.py

import math


###############################################################
# SYSTEM VOLTAGE SELECTION
###############################################################

def determine_system_voltage(load_watts):
    """
    Select a practical DC system voltage.

    Engineering guideline:

        <= 1000 W   -> 12V
        <= 3000 W   -> 24V
        <= 8000 W   -> 48V
        > 8000 W    -> 96V
    """

    if load_watts <= 1000:
        return 12

    if load_watts <= 3000:
        return 24

    if load_watts <= 8000:
        return 48

    return 96


###############################################################
# BATTERY BANK CALCULATION
###############################################################

def calculate_battery_bank(
    load_watts,
    daily_energy,
    autonomy_days,
    battery,
    inverter_efficiency=0.95,
):
    """
    Battery Bank Engineering Engine

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

    if battery is None:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": "No battery selected.",

            "warnings": [
                "Battery selection is required."
            ]
        }

    ###########################################################
    # SYSTEM VOLTAGE
    ###########################################################

    system_voltage = determine_system_voltage(
        load_watts
    )

    ###########################################################
    # BATTERY TYPE FACTORS
    ###########################################################

    battery_type = (
        battery.battery_type or ""
    ).lower()

    if "lith" in battery_type:

        temperature_factor = 1.00
        ageing_factor = 1.05

    else:

        temperature_factor = 1.15
        ageing_factor = 1.10

    ###########################################################
    # DEPTH OF DISCHARGE
    ###########################################################

    dod = battery.depth_of_discharge

    if dod > 1:
        dod /= 100

    if dod <= 0:
        dod = 0.50
        warnings.append(
            "Battery depth of discharge was invalid. 50% used."
        )

    ###########################################################
    # BATTERY EFFICIENCY
    ###########################################################

    if inverter_efficiency <= 0:

        inverter_efficiency = 0.95

        warnings.append(
            "Invalid inverter efficiency supplied."
        )

    ###########################################################
    # REQUIRED BATTERY ENERGY
    ###########################################################

    required_energy = (

        daily_energy
        * autonomy_days
        * temperature_factor
        * ageing_factor

        /

        (
            dod
            * inverter_efficiency
        )

    )

    ###########################################################
    # REQUIRED CAPACITY
    ###########################################################

    required_capacity = (

        required_energy

        /

        system_voltage

    )

    ###########################################################
    # SERIES BATTERIES
    ###########################################################

    series = max(

        1,

        math.ceil(

            system_voltage

            /

            battery.voltage

        )

    )

    ###########################################################
    # PARALLEL STRINGS
    ###########################################################

    parallel = max(

        1,

        math.ceil(

            required_capacity

            /

            battery.capacity_ah

        )

    )

    ###########################################################
    # TOTAL BATTERIES
    ###########################################################

    quantity = (

        series
        * parallel

    )

    ###########################################################
    # INSTALLED BANK
    ###########################################################

    bank_voltage = series * battery.voltage

    bank_capacity = (

        parallel
        * battery.capacity_ah

    )

    bank_energy = (

        bank_voltage
        * bank_capacity

    )

    ###########################################################
    # UTILIZATION
    ###########################################################

    utilization = (

        required_energy

        /

        bank_energy

    ) * 100

    ###########################################################
    # RESPONSE
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

            "system_voltage":
                system_voltage,

            "energy_wh":
                round(
                    required_energy,
                    2
                ),

            "capacity_ah":
                round(
                    required_capacity,
                    2
                ),
                "quantity":
                quantity,

        },

        #######################################################
        # SELECTED BATTERY BANK
        #######################################################

        "selected": {

            "object":
                battery,

            "name":
                str(battery),

            "battery_type":
                battery.battery_type,

            "voltage":
                battery.voltage,

            "capacity":
                battery.capacity_ah,

            "series":
                series,

            "parallel":
                parallel,

            "quantity":
                quantity,

            "bank_voltage":
                round(
                    bank_voltage,
                    2
                ),

            "bank_capacity":
                round(
                    bank_capacity,
                    2
                ),

            "bank_energy":
                round(
                    bank_energy,
                    2
                ),

            "dod":
                round(
                    dod * 100,
                    1
                ),

            "temperature_factor":
                temperature_factor,

            "ageing_factor":
                ageing_factor,

            "efficiency":
                inverter_efficiency,

            "utilization":
                round(
                    utilization,
                    2
                ),

            "price":
                battery.price,
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