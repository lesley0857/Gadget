# solar/services/battery_engine.py

import math

###############################################################

# BATTERY BANK DESIGN ENGINE

###############################################################

def calculate_battery_bank(
    load_watts,

    daily_energy,

    battery,

    system_voltage,

    inverter_efficiency=0.95,

    operating_mode="off_grid",
    ):

    warnings = []


    ###########################################################
    # VALIDATE BATTERY
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

            ],

        }


    ###########################################################
    # VALIDATE LOAD POWER
    ###########################################################

    try:

        load_watts = float(

            load_watts or 0

        )

    except (

        TypeError,

        ValueError,

    ):

        load_watts = 0

        warnings.append(

            "Invalid load power supplied. "

            "Zero was used."

        )


    if load_watts < 0:

        load_watts = 0

        warnings.append(

            "Load power cannot be negative."

        )


    ###########################################################
    # VALIDATE DAILY ENERGY
    ###########################################################

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

            "Invalid daily energy supplied. "

            "Zero was used."

        )


    if daily_energy < 0:

        daily_energy = 0

        warnings.append(

            "Daily energy cannot be negative."

        )


    ###########################################################
    # VALIDATE SYSTEM VOLTAGE
    ###########################################################

    try:

        system_voltage = float(

            system_voltage

        )

    except (

        TypeError,

        ValueError,

    ):

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": (

                "Invalid system voltage."

            ),

            "warnings": [

                "System voltage must be greater than zero."

            ],

        }


    if system_voltage <= 0:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": (

                "Invalid system voltage."

            ),

            "warnings": [

                "System voltage must be greater than zero."

            ],

        }


    ###########################################################
    # VALIDATE OPERATING MODE
    ###########################################################

    valid_modes = [

        "off_grid",

        "solar_battery",

        "backup",

    ]


    if operating_mode not in valid_modes:

        operating_mode = "off_grid"

        warnings.append(

            "Invalid operating mode. "

            "Off-grid mode was used."

        )


    ###########################################################
    # VALIDATE INVERTER EFFICIENCY
    ###########################################################

    try:

        inverter_efficiency = float(

            inverter_efficiency

        )

    except (

        TypeError,

        ValueError,

    ):

        inverter_efficiency = 0.95

        warnings.append(

            "Invalid inverter efficiency. "

            "95% was used."

        )


    if not (

        0 < inverter_efficiency <= 1

    ):

        inverter_efficiency = 0.95

        warnings.append(

            "Invalid inverter efficiency. "

            "95% was used."

        )


    ###########################################################
    # BATTERY SPECIFICATIONS
    ###########################################################

    battery_voltage = getattr(

        battery,

        "voltage",

        None

    )


    battery_capacity = getattr(

        battery,

        "capacity_ah",

        None

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


    try:

        battery_capacity = float(

            battery_capacity

        )

    except (

        TypeError,

        ValueError,

    ):

        battery_capacity = 0


    if battery_voltage <= 0:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": (

                "Selected battery has "

                "an invalid voltage."

            ),

            "warnings": [

                "Battery voltage must be greater than zero."

            ],

        }


    if battery_capacity <= 0:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": (

                "Selected battery has "

                "invalid capacity."

            ),

            "warnings": [

                "Battery capacity must be greater than zero."

            ],

        }


    ###########################################################
    # BATTERY DEPTH OF DISCHARGE
    ###########################################################

    dod = getattr(

        battery,

        "depth_of_discharge",

        0.50

    )


    try:

        dod = float(

            dod

        )

    except (

        TypeError,

        ValueError,

    ):

        dod = 0.50

        warnings.append(

            "Invalid battery depth of discharge. "

            "50% was used."

        )


    if dod > 1:

        dod /= 100


    if not (

        0 < dod <= 1

    ):

        dod = 0.50

        warnings.append(

            "Invalid battery depth of discharge. "

            "50% was used."

        )


    ###########################################################
    # BATTERY ENERGY REQUIREMENT
    ###########################################################

    if operating_mode == "off_grid":

        battery_energy_requirement = daily_energy


    elif operating_mode == "solar_battery":

        battery_energy_requirement = (

            daily_energy

            *

            0.50

        )


    else:

        battery_energy_requirement = (

            daily_energy

            *

            0.30

        )


    ###########################################################
    # BATTERY TYPE FACTORS
    ###########################################################

    battery_type = (

        getattr(

            battery,

            "battery_type",

            ""

        )

        or ""

    ).lower()


    if "lith" in battery_type:

        temperature_factor = 1.00

        ageing_factor = 1.05


    else:

        temperature_factor = 1.15

        ageing_factor = 1.10


    ###########################################################
    # REQUIRED BATTERY ENERGY
    ###########################################################

    required_energy = (

        battery_energy_requirement

        *

        temperature_factor

        *

        ageing_factor

        /

        (

            dod

            *

            inverter_efficiency

        )

    )


    ###########################################################
    # REQUIRED BATTERY CAPACITY
    ###########################################################

    required_capacity = (

        required_energy

        /

        system_voltage

    )


    ###########################################################
    # BATTERY SERIES CONFIGURATION
    ###########################################################

    series = (

        system_voltage

        /

        battery_voltage

    )


    if not series.is_integer():

        return {

            "success": False,

            "required": {

                "system_voltage":

                    system_voltage,

                "battery_voltage":

                    battery_voltage,

            },

            "selected": None,

            "closest": None,

            "message": (

                "The selected battery voltage cannot "

                "be configured to exactly achieve the "

                "selected system voltage."

            ),

            "warnings": [

                (

                    "System voltage must be an exact "

                    "multiple of the selected battery voltage."

                )

            ],

        }


    series = int(

        series

    )


    if series < 1:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message": (

                "Selected battery voltage is higher "

                "than the system voltage."

            ),

            "warnings": [

                (

                    "Battery voltage cannot exceed "

                    "the selected system voltage."

                )

            ],

        }


    ###########################################################
    # BATTERY PARALLEL CONFIGURATION
    ###########################################################

    parallel = max(

        1,

        math.ceil(

            required_capacity

            /

            battery_capacity

        )

    )


    ###########################################################
    # TOTAL BATTERY QUANTITY
    ###########################################################

    quantity = (

        series

        *

        parallel

    )


    ###########################################################
    # ACTUAL BANK VOLTAGE
    ###########################################################

    bank_voltage = (

        series

        *

        battery_voltage

    )


    ###########################################################
    # ACTUAL BANK CAPACITY
    ###########################################################

    bank_capacity = (

        parallel

        *

        battery_capacity

    )


    ###########################################################
    # ACTUAL BANK ENERGY
    ###########################################################

    bank_energy = (

        bank_voltage

        *

        bank_capacity

    )


    ###########################################################
    # USABLE BANK ENERGY
    ###########################################################

    usable_energy = (

        bank_energy

        *

        dod

        *

        inverter_efficiency

    )


    ###########################################################
    # BATTERY UTILIZATION
    ###########################################################

    utilization = (

        required_energy

        /

        bank_energy

        *

        100

    ) if bank_energy > 0 else 0


    ###########################################################
    # DESIGN WARNINGS
    ###########################################################

    if utilization > 90:

        warnings.append(

            "Battery bank is operating near "

            "its usable capacity."

        )


    if utilization < 25:

        warnings.append(

            "Selected battery bank is significantly "

            "larger than required."

        )


    ###########################################################
    # FINAL RESPONSE
    ###########################################################

    return {

        "success": True,

        "required": {

            "system_voltage":

                round(

                    system_voltage,

                    2

                ),

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

            "series":

                series,

            "parallel":

                parallel,

        },

        "selected": {

            "object":

                battery,

            "name":

                str(

                    battery

                ),

            "battery_type":

                battery.battery_type,

            "voltage":

                battery_voltage,

            "capacity":

                battery_capacity,

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

            "usable_energy":

                round(

                    usable_energy,

                    2

                ),

            "dod":

                round(

                    dod

                    *

                    100,

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

        "closest":

            None,

        "message":

            None,

        "warnings":

            warnings,

    }

