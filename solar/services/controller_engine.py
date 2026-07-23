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
    Industrial Solar Charge Controller Selection Engine

    -----------------------------------------------------------
    PURPOSE
    -----------------------------------------------------------

    Select a charge controller capable of safely handling:

        1. Battery-system voltage

        2. PV array operating voltage

        3. PV array current

        4. PV array power

        5. Expected MPPT charging current

    -----------------------------------------------------------
    IMPORTANT ENGINEERING PRINCIPLE
    -----------------------------------------------------------

    For an MPPT charge controller:

        PV power is converted into charging current
        at the battery voltage.

    Therefore:

        Approximate charging current

        =
        PV power
        /
        Battery voltage

    The controller must therefore be checked against:

        1. Maximum PV input voltage

        2. Maximum charging current

        3. Maximum PV input power

    -----------------------------------------------------------
    RETURN STRUCTURE
    -----------------------------------------------------------

    {

        success,

        required,

        selected,

        closest,

        message,

        warnings

    }

    """


    ###########################################################
    # WARNINGS
    ###########################################################

    warnings = []


    ###########################################################
    # VALIDATE BATTERY VOLTAGE
    ###########################################################

    try:

        battery_voltage = float(

            battery_voltage

        )

    except (

        TypeError,

        ValueError

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
    # VALIDATE ARRAY VOLTAGE
    ###########################################################

    try:

        array_voltage = float(

            array_voltage

        )

    except (

        TypeError,

        ValueError

    ):

        array_voltage = 0

        warnings.append(

            "Invalid PV array voltage supplied. "
            "Zero was used."

        )


    if array_voltage < 0:

        array_voltage = 0

        warnings.append(

            "PV array voltage cannot be negative. "
            "Zero was used."

        )


    ###########################################################
    # VALIDATE ARRAY CURRENT
    ###########################################################

    try:

        array_current = float(

            array_current

        )

    except (

        TypeError,

        ValueError

    ):

        array_current = 0

        warnings.append(

            "Invalid PV array current supplied. "
            "Zero was used."

        )


    if array_current < 0:

        array_current = 0

        warnings.append(

            "PV array current cannot be negative. "
            "Zero was used."

        )


    ###########################################################
    # VALIDATE ARRAY POWER
    ###########################################################

    try:

        array_power = float(

            array_power

        )

    except (

        TypeError,

        ValueError

    ):

        array_power = 0

        warnings.append(

            "Invalid PV array power supplied. "
            "Zero was used."

        )


    if array_power < 0:

        array_power = 0

        warnings.append(

            "PV array power cannot be negative. "
            "Zero was used."

        )


    ###########################################################
    # VALIDATE SAFETY FACTOR
    ###########################################################

    try:

        safety_factor = float(

            safety_factor

        )

    except (

        TypeError,

        ValueError

    ):

        safety_factor = 1.25

        warnings.append(

            "Invalid controller safety factor. "
            "25% margin was used."

        )


    if safety_factor < 1:

        safety_factor = 1.25

        warnings.append(

            "Controller safety factor cannot be below 1.0. "
            "25% margin was used."

        )


    ###########################################################
    # PV VOLTAGE SAFETY MARGIN
    ###########################################################

    """

    The controller must be able to tolerate the PV array
    voltage under normal operating conditions.

    A 10% design margin is applied.

    """

    required_pv_voltage = (

        array_voltage

        *

        1.10

    )


    ###########################################################
    # PV CURRENT SAFETY MARGIN
    ###########################################################

    """

    This is the actual PV input-current requirement.

    It is used as an additional input check.

    """

    required_pv_current = (

        array_current

        *

        safety_factor

    )


    ###########################################################
    # MPPT CHARGE CURRENT
    ###########################################################

    """

    MPPT controllers convert PV power into charging current
    at the battery voltage.

    Approximate charging current:

        PV power
        /
        Battery voltage

    The 25% safety margin is then applied.

    """

    if battery_voltage > 0:

        estimated_charge_current = (

            array_power

            /

            battery_voltage

        )

    else:

        estimated_charge_current = 0


    required_charge_current = (

        estimated_charge_current

        *

        safety_factor

    )


    ###########################################################
    # REQUIRED PV POWER
    ###########################################################

    required_pv_power = (

        array_power

        *

        safety_factor

    )


    ###########################################################
    # REQUIRED DESIGN
    ###########################################################

    required = {

        "battery_voltage":

            battery_voltage,

        "pv_voltage":

            round(

                required_pv_voltage,

                2

            ),

        "pv_current":

            round(

                required_pv_current,

                2

            ),

        "charge_current":

            round(

                required_charge_current,

                2

            ),

        "pv_power":

            round(

                required_pv_power,

                2

            ),

    }


    ###########################################################
    # SEARCH FOR SUITABLE CONTROLLER
    ###########################################################

    controller = (

        ChargeController.objects

        .filter(

            active=True,

            battery_voltage=battery_voltage,

            max_pv_voltage__gte=

                required_pv_voltage,

            max_charge_current__gte=

                required_charge_current,

        )

        .order_by(

            "max_charge_current",

            "max_pv_voltage",

        )

        .first()

    )


    ###########################################################
    # CONTROLLER FOUND
    ###########################################################

    if controller:

        #######################################################
        # CURRENT UTILIZATION
        #######################################################

        current_utilization = (

            required_charge_current

            /

            controller.max_charge_current

        ) * 100


        #######################################################
        # PV VOLTAGE UTILIZATION
        #######################################################

        voltage_utilization = (

            required_pv_voltage

            /

            controller.max_pv_voltage

        ) * 100


        #######################################################
        # CONTROLLER CHARGING POWER
        #######################################################

        controller_power = (

            battery_voltage

            *

            controller.max_charge_current

        )


        #######################################################
        # POWER UTILIZATION
        #######################################################

        if controller_power > 0:

            power_utilization = (

                required_pv_power

                /

                controller_power

            ) * 100

        else:

            power_utilization = 0


        #######################################################
        # WARNINGS
        #######################################################

        if current_utilization > 90:

            warnings.append(

                "Required charging current exceeds "
                "90% of controller rating."

            )


        if voltage_utilization > 90:

            warnings.append(

                "PV voltage is close to the controller "
                "maximum PV voltage."

            )


        if power_utilization > 90:

            warnings.append(

                "PV power is close to the estimated "
                "controller charging capacity."

            )


        #######################################################
        # RETURN SUCCESS
        #######################################################

        return {

            "success": True,

            "required":

                required,

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

            "closest":

                None,

            "message":

                None,

            "warnings":

                warnings,

        }


    ###########################################################
    # FIND CLOSEST CONTROLLER
    ###########################################################

    """

    No controller satisfies the complete requirements.

    Find the controller with the smallest engineering gap.

    The closest controller is selected based on the
    combined requirements for:

        1. Charge current

        2. PV voltage

    """

    available_controllers = (

        ChargeController.objects

        .filter(

            active=True,

            battery_voltage=battery_voltage,

        )

        .order_by(

            "max_charge_current",

            "max_pv_voltage",

        )

    )


    closest = None

    closest_score = None


    for candidate in available_controllers:

        #######################################################
        # CURRENT GAP
        #######################################################

        current_gap = max(

            0,

            required_charge_current

            -

            candidate.max_charge_current

        )


        #######################################################
        # VOLTAGE GAP
        #######################################################

        voltage_gap = max(

            0,

            required_pv_voltage

            -

            candidate.max_pv_voltage

        )


        #######################################################
        # POWER GAP
        #######################################################

        candidate_power = (

            battery_voltage

            *

            candidate.max_charge_current

        )


        power_gap = max(

            0,

            required_pv_power

            -

            candidate_power

        )


        #######################################################
        # TOTAL ENGINEERING GAP
        #######################################################

        score = (

            current_gap

            +

            voltage_gap

            +

            (

                power_gap

                /

                max(

                    battery_voltage,

                    1

                )

            )

        )


        if (

            closest_score is None

            or

            score < closest_score

        ):

            closest = candidate

            closest_score = score


    ###########################################################
    # CLOSEST DATA
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

        "No charge controller satisfies the complete "
        "engineering requirements."

    )


    ###########################################################
    # RETURN FAILURE
    ###########################################################

    return {

        "success":

            False,

        "required":

            required,

        "selected":

            None,

        "closest":

            closest_data,

        "message":

            "No suitable charge controller found.",

        "warnings":

            warnings,

    }
