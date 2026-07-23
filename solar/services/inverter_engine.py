# solar/services/inverter_engine.py

from solar.models import Inverter

###############################################################

# INVERTER SELECTION ENGINE

###############################################################

def select_inverter(
running_load,
surge_load,
battery_voltage,
safety_factor=1.20,
):
    """
    Select an inverter compatible with the calculated system voltage.

    ```
    The inverter must satisfy:

        1. Battery/DC system voltage
        2. Continuous running-load requirement
        3. Surge-load requirement

    Returns:

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
    # VALIDATE RUNNING LOAD
    ###########################################################

    try:

        running_load = float(
            running_load or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        running_load = 0

        warnings.append(
            "Invalid running load supplied. "
            "Zero was used."
        )

    if running_load < 0:

        running_load = 0

        warnings.append(
            "Running load cannot be negative. "
            "Zero was used."
        )

    ###########################################################
    # VALIDATE SURGE LOAD
    ###########################################################

    try:

        surge_load = float(
            surge_load or 0
        )

    except (
        TypeError,
        ValueError,
    ):

        surge_load = running_load

        warnings.append(
            "Invalid surge load supplied. "
            "Running load was used."
        )

    if surge_load < 0:

        surge_load = running_load

        warnings.append(
            "Surge load cannot be negative. "
            "Running load was used."
        )

    ###########################################################
    # SURGE CANNOT BE BELOW RUNNING LOAD
    ###########################################################

    if surge_load < running_load:

        surge_load = running_load

        warnings.append(
            "Surge load was below running load. "
            "Running load was used as the surge load."
        )

    ###########################################################
    # VALIDATE SYSTEM VOLTAGE
    ###########################################################

    try:

        battery_voltage = float(
            battery_voltage
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

            "message":
                "Invalid battery-system voltage.",

            "warnings": [

                "Battery voltage must be greater than zero."

            ],

        }

    if battery_voltage <= 0:

        return {

            "success": False,

            "required": {},

            "selected": None,

            "closest": None,

            "message":
                "Invalid battery-system voltage.",

            "warnings": [

                "Battery voltage must be greater than zero."

            ],

        }

    ###########################################################
    # VALIDATE SAFETY FACTOR
    ###########################################################

    try:

        safety_factor = float(
            safety_factor
        )

    except (
        TypeError,
        ValueError,
    ):

        safety_factor = 1.20

        warnings.append(
            "Invalid inverter safety factor. "
            "20% margin was used."
        )

    if safety_factor < 1:

        safety_factor = 1.20

        warnings.append(
            "Inverter safety factor cannot be below 1.0. "
            "20% margin was used."
        )

    ###########################################################
    # ENGINEERING REQUIREMENTS
    ###########################################################

    required_continuous_power = (

        running_load

        *

        safety_factor

    )

    required_surge_power = (

        surge_load

        *

        1.10

    )

    required = {

        "battery_voltage":
            battery_voltage,

        "continuous_power":
            round(
                required_continuous_power,
                2
            ),

        "surge_power":
            round(
                required_surge_power,
                2
            ),

    }

    ###########################################################
    # SEARCH FOR COMPATIBLE INVERTERS
    ###########################################################

    compatible_inverters = (

        Inverter.objects

        .filter(

            active=True,

            dc_voltage=battery_voltage,

            rated_power__gte=(
                required_continuous_power
            ),

            surge_power__gte=(
                required_surge_power
            ),

        )

        .order_by(

            "rated_power",

            "surge_power",

        )

    )

    ###########################################################
    # SELECT SMALLEST SUITABLE INVERTER
    ###########################################################

    inverter = (

        compatible_inverters

        .first()

    )

    ###########################################################
    # SUITABLE INVERTER FOUND
    ###########################################################

    if inverter:

        running_utilization = (

            running_load

            /

            float(
                inverter.rated_power
            )

        ) * 100

        surge_utilization = (

            surge_load

            /

            float(
                inverter.surge_power
            )

        ) * 100

        #######################################################
        # UTILIZATION WARNINGS
        #######################################################

        if running_utilization > 80:

            warnings.append(
                "Running load is using more than "
                "80% of the inverter continuous rating."
            )

        if surge_utilization > 80:

            warnings.append(
                "Surge load is using more than "
                "80% of the inverter surge capacity."
            )

        #######################################################
        # RETURN SELECTED INVERTER
        #######################################################

        return {

            "success": True,

            "required":
                required,

            "selected": {

                "object":
                    inverter,

                "name":
                    str(inverter),

                "brand":
                    inverter.brand,

                "model":
                    inverter.model,

                "battery_voltage":
                    inverter.dc_voltage,

                "rated_power":
                    inverter.rated_power,

                "surge_power":
                    inverter.surge_power,

                "utilization":
                    round(
                        running_utilization,
                        2
                    ),

                "surge_utilization":
                    round(
                        surge_utilization,
                        2
                    ),

                "price":
                    inverter.price,

            },

            "closest":
                None,

            "message":
                None,

            "warnings":
                warnings,

        }

    ###########################################################
    # FIND CLOSEST COMPATIBLE INVERTER
    ###########################################################

    available_inverters = (

        Inverter.objects

        .filter(

            active=True,

            dc_voltage=battery_voltage,

        )

        .order_by(

            "rated_power",

            "surge_power",

        )

    )

    ###########################################################
    # FIND BEST ALTERNATIVE
    ###########################################################

    closest = None

    closest_score = None

    for candidate in available_inverters:

        continuous_gap = max(

            0,

            required_continuous_power

            -

            float(
                candidate.rated_power
            )

        )

        surge_gap = max(

            0,

            required_surge_power

            -

            float(
                candidate.surge_power
            )

        )

        total_gap = (

            continuous_gap

            +

            surge_gap

        )

        if (

            closest_score is None

            or

            total_gap < closest_score

        ):

            closest = candidate

            closest_score = total_gap

    ###########################################################
    # CLOSEST INVERTER DATA
    ###########################################################

    closest_data = None

    if closest:

        closest_data = {

            "object":
                closest,

            "name":
                str(closest),

            "brand":
                closest.brand,

            "model":
                closest.model,

            "battery_voltage":
                closest.dc_voltage,

            "rated_power":
                closest.rated_power,

            "surge_power":
                closest.surge_power,

            "price":
                closest.price,

        }

    ###########################################################
    # FAILURE
    ###########################################################

    warnings.append(
        "No inverter satisfies the complete "
        "engineering requirements."
    )

    ###########################################################
    # RETURN FAILURE
    ###########################################################

    return {

        "success": False,

        "required":
            required,

        "selected":
            None,

        "closest":
            closest_data,

        "message":
            "No suitable inverter found.",

        "warnings":
            warnings,

    }

