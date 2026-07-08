from solar.models import Cable
from decimal import Decimal
###############################################################
# CONSTANTS
###############################################################

COPPER_RESISTIVITY = 0.0175

STANDARD_SIZES = [

    1.5,
    2.5,
    4,
    6,
    10,
    16,
    25,
    35,
    50,
    70,
    95,
    120,
    150,
    185,
    240,
    300,

]


###############################################################
# MARKET SIZE
###############################################################

def nearest_market_size(size):

    for s in STANDARD_SIZES:

        if s >= size:
            return s

    return STANDARD_SIZES[-1]


###############################################################
# STANDARD CABLE ENGINE
###############################################################

def _calculate_cable(

    current,
    voltage,
    distance,
    cable_type,
    max_voltage_drop=3,

):

    warnings = []

    ###########################################################
    # REQUIRED SIZE
    ###########################################################

    allowable_drop = (

        voltage
        *
        max_voltage_drop
        / 100

    )

    calculated_size = (

        2
        *
        COPPER_RESISTIVITY
        *
        current
        *
        distance

        /

        allowable_drop

    )

    required_size = nearest_market_size(
        calculated_size
    )

    ###########################################################
    # SEARCH DATABASE
    ###########################################################

    cable = (

        Cable.objects

        .filter(

            active=True,

            cable_type=cable_type,

            size_mm__gte=required_size,

            ampacity__gte=current,

        )

        .order_by("size_mm")

        .first()

    )

    ###########################################################
    # CLOSEST AVAILABLE
    ###########################################################

    closest = (

        Cable.objects

        .filter(

            active=True,

            cable_type=cable_type

        )

        .order_by("-ampacity")

        .first()

    )

    ###########################################################
    # FAILURE
    ###########################################################

    if cable is None:

        warnings.append(
            "Suitable cable not found."
        )

        return {

            "success": False,

            "required": {

                "size": required_size,

                "current": round(current,2),

                "distance": distance,

                "length": distance * 2,

                "voltage": voltage,

                "max_voltage_drop": max_voltage_drop,

            },

            "selected": None,

            "closest":

                {

                    "object": closest,

                    "manufacturer": closest.manufacturer,

                    "name": closest.name,

                    "size": closest.size_mm,

                    "ampacity": closest.ampacity,

                    "unit_price": closest.price_per_meter,

                }

                if closest

                else None,

            "message":

                "No suitable cable found.",

            "warnings": warnings,

        }
        ###########################################################
    # SUCCESS
    ###########################################################

    actual_drop = (

        2
        *
        COPPER_RESISTIVITY
        *
        current
        *
        distance

        /

        cable.size_mm

    )

    voltage_drop = (

        actual_drop

        /

        voltage

    ) * 100

    ###########################################################
    # CABLE LENGTH
    ###########################################################

    length = distance * 2

    ###########################################################
    # TOTAL PRICE
    ###########################################################

    unit_price = cable.price_per_meter

    total_price = unit_price * Decimal(str(length))

    ###########################################################
    # ENGINEERING WARNINGS
    ###########################################################

    if voltage_drop > max_voltage_drop:

        warnings.append(
            "Voltage drop exceeds allowable limit."
        )

    if current > cable.ampacity * 0.90:

        warnings.append(
            "Cable loading exceeds 90% of ampacity."
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
        # REQUIRED
        #######################################################

        "required": {

            "size":
                required_size,

            "current":
                round(current,2),

            "distance":
                distance,

            "length":
                length,

            "voltage":
                voltage,

            "max_voltage_drop":
                max_voltage_drop,
        },

        #######################################################
        # SELECTED
        #######################################################

        "selected": {

            "object":
                cable,

            "manufacturer":
                cable.manufacturer,

            "name":
                cable.name,

            "size":
                cable.size_mm,

            "ampacity":
                cable.ampacity,

            "length":
                length,

            "unit_price":
                unit_price,

            "total_price":
                total_price,

            "voltage_drop":
                round(
                    voltage_drop,
                    2
                ),
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

        "warnings":
            warnings,
    }


###############################################################
# PV CABLE
###############################################################

def calculate_dc_cable(
    current,
    voltage,
    distance,
):

    return _calculate_cable(

        current=current,

        voltage=voltage,

        distance=distance,

        cable_type="pv",

        max_voltage_drop=3,

    )


###############################################################
# BATTERY CABLE
###############################################################

def battery_cable(
    inverter_power,
    battery_voltage,
    efficiency=0.90,
    distance=2,
):

    current = (

        inverter_power

        /

        (

            battery_voltage

            *

            efficiency

        )

    ) * 1.25

    return _calculate_cable(

        current=current,

        voltage=battery_voltage,

        distance=distance,

        cable_type="battery",

        max_voltage_drop=3,

    )


###############################################################
# AC CABLE
###############################################################

def calculate_ac_cable(
    power,
    voltage,
    distance,
):

    current = (

        power

        /

        voltage

    ) * 1.25

    return _calculate_cable(

        current=current,

        voltage=voltage,

        distance=distance,

        cable_type="ac",

        max_voltage_drop=3,

    )


###############################################################
# EARTH CABLE
###############################################################

def earth_cable(
    phase_size,
    distance=5,
):

    if phase_size <= 16:

        current = 16

    elif phase_size <= 35:

        current = 35

    else:

        current = phase_size

    return _calculate_cable(

        current=current,

        voltage=230,

        distance=distance,

        cable_type="earth",

        max_voltage_drop=5,

    )