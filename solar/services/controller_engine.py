# solar/services/controller_engine.py

from solar.models import ChargeController


###############################################################
# CHARGE CONTROLLER SELECTION ENGINE
###############################################################

def select_controller(
    battery_voltage,
    array_voltage,
    array_current,
    array_power,
    safety_factor=1.25,
):
    """
    Standardized Charge Controller Engine

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
    # REQUIRED SPECIFICATIONS
    ###########################################################

    required_current = (
        array_current
        * safety_factor
    )

    required_voltage = (
        array_voltage
        * 1.10
    )

    required = {

        "battery_voltage":
            battery_voltage,

        "pv_voltage":
            round(
                required_voltage,
                2
            ),

        "charge_current":
            round(
                required_current,
                2
            ),

        "pv_power":
            round(
                array_power,
                2
            ),
    }

    ###########################################################
    # SEARCH DATABASE
    ###########################################################

    controller = (

        ChargeController.objects

        .filter(

            active=True,

            battery_voltage=battery_voltage,

            max_pv_voltage__gte=required_voltage,

            max_charge_current__gte=required_current

        )

        .order_by(

            "max_charge_current"

        )

        .first()

    )

    ###########################################################
    # FOUND
    ###########################################################

    if controller:

        current_utilization = (

            array_current

            /

            controller.max_charge_current

        ) * 100

        voltage_utilization = (

            array_voltage

            /

            controller.max_pv_voltage

        ) * 100

        controller_power = (

            battery_voltage
            *
            controller.max_charge_current

        )

        power_utilization = (

            array_power

            /

            controller_power

        ) * 100

        #######################################################
        # WARNINGS
        #######################################################

        if current_utilization > 90:

            warnings.append(
                "Charge current exceeds 90% of controller rating."
            )

        if voltage_utilization > 90:

            warnings.append(
                "PV voltage exceeds 90% of controller rating."
            )

        if power_utilization > 90:

            warnings.append(
                "PV power exceeds 90% of controller capacity."
            )

        #######################################################
        # RETURN
        #######################################################

        return {

            ###################################################
            # STATUS
            ###################################################

            "success": True,

            ###################################################
            # REQUIRED
            ###################################################

            "required":
                required,

            ###################################################
            # SELECTED
            ###################################################

            "selected": {

                "object":
                    controller,

                "name":
                    str(controller),

                "brand":
                    controller.brand,

                "model":
                    controller.model,

                "battery_voltage":
                    controller.battery_voltage,

                "max_pv_voltage":
                    controller.max_pv_voltage,

                "max_charge_current":
                    controller.max_charge_current,

                "controller_power":
                    round(
                        controller_power,
                        2
                    ),

                "current_utilization":
                    round(
                        current_utilization,
                        2
                    ),

                "voltage_utilization":
                    round(
                        voltage_utilization,
                        2
                    ),

                "power_utilization":
                    round(
                        power_utilization,
                        2
                    ),

                "price":
                    controller.price,
            },

            ###################################################
            # CLOSEST
            ###################################################

            "closest": None,

            ###################################################
            # MESSAGE
            ###################################################

            "message": None,

            ###################################################
            # WARNINGS
            ###################################################

            "warnings": warnings,
        }

    ###########################################################
    # CLOSEST AVAILABLE
    ###########################################################

    closest = (

        ChargeController.objects

        .filter(

            active=True,

            battery_voltage=battery_voltage

        )

        .order_by(

            "-max_charge_current"

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
                closest.battery_voltage,

            "max_pv_voltage":
                closest.max_pv_voltage,

            "max_charge_current":
                closest.max_charge_current,

            "price":
                closest.price,
        }

    ###########################################################
    # FAILURE
    ###########################################################

    warnings.append(
        "No charge controller satisfies the engineering requirements."
    )

    return {

        ###################################################
        # STATUS
        ###################################################

        "success": False,

        ###################################################
        # REQUIRED
        ###################################################

        "required":
            required,

        ###################################################
        # SELECTED
        ###################################################

        "selected": None,

        ###################################################
        # CLOSEST
        ###################################################

        "closest":
            closest_data,

        ###################################################
        # MESSAGE
        ###################################################

        "message":
            "No suitable charge controller found.",

        ###################################################
        # WARNINGS
        ###################################################

        "warnings":
            warnings,
    }