from solar.models import Inverter


###############################################################
# INVERTER SELECTION ENGINE
###############################################################

def select_inverter(
    running_load,
    surge_load,
    battery_voltage,
    safety_factor=1.25,
):
    """
    Standardized Inverter Engine

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
    # REQUIRED POWER
    ###########################################################

    required_continuous = (
        running_load
        * safety_factor
    )

    required_surge = (
        surge_load
        * 1.10
    )

    required = {

        "battery_voltage":
            battery_voltage,

        "continuous_power":
            round(
                required_continuous,
                2
            ),

        "surge_power":
            round(
                required_surge,
                2
            ),
    }

    ###########################################################
    # SEARCH DATABASE
    ###########################################################

    inverter = (

        Inverter.objects

        .filter(

            active=True,

            dc_voltage=battery_voltage,

            rated_power__gte=required_continuous,

            surge_power__gte=required_surge

        )

        .order_by(

            "rated_power"

        )

        .first()

    )

    ###########################################################
    # FOUND
    ###########################################################

    if inverter:

        utilization = (

            running_load

            /

            inverter.rated_power

        ) * 100

        surge_utilization = (

            surge_load

            /

            inverter.surge_power

        ) * 100

        if utilization > 90:

            warnings.append(
                "Running load exceeds 90% of inverter rating."
            )

        if surge_utilization > 90:

            warnings.append(
                "Surge load exceeds 90% of inverter surge capacity."
            )

        return {

            ####################################################
            # STATUS
            ####################################################

            "success": True,

            ####################################################
            # REQUIRED
            ####################################################

            "required": required,

            ####################################################
            # SELECTED
            ####################################################

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
                        utilization,
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

            ####################################################
            # CLOSEST
            ####################################################

            "closest": None,

            ####################################################
            # MESSAGE
            ####################################################

            "message": None,

            ####################################################
            # WARNINGS
            ####################################################

            "warnings": warnings,
        }

    ###########################################################
    # CLOSEST AVAILABLE
    ###########################################################

    closest = (

        Inverter.objects

        .filter(

            active=True,

            dc_voltage=battery_voltage

        )

        .order_by(

            "-rated_power"

        )

        .first()

    )

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
        "No inverter satisfies the engineering requirements."
    )

    return {

        ####################################################
        # STATUS
        ####################################################

        "success": False,

        ####################################################
        # REQUIRED
        ####################################################

        "required": required,

        ####################################################
        # SELECTED
        ####################################################

        "selected": None,

        ####################################################
        # CLOSEST
        ####################################################

        "closest": closest_data,

        ####################################################
        # MESSAGE
        ####################################################

        "message":
            "No suitable inverter found.",

        ####################################################
        # WARNINGS
        ####################################################

        "warnings": warnings,
    }