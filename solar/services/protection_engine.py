from solar.models import (
    Fuse,
    Breaker,
    SPD,
    Isolator
)


####################################################
# GENERIC PROTECTION SELECTOR
####################################################

###############################################################
# STANDARD PROTECTION ENGINE
###############################################################

def _select_protection(

    model,
    filters,
    order_field,
    required,
    closest_filters=None,

):
    """
    Standard Protection Engine

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
    # SEARCH DATABASE
    ###########################################################

    device = (

        model.objects

        .filter(

            active=True,

            **filters

        )

        .order_by(

            order_field

        )

        .first()

    )

    ###########################################################
    # SUCCESS
    ###########################################################

    if device:

        rating = getattr(

            device,

            "current_rating",

            getattr(

                device,

                "voltage_rating",

                None

            )

        )

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
                    device,

                "name":
                    str(device),

                "manufacturer":
                    getattr(
                        device,
                        "manufacturer",
                        ""
                    ),

                "rating":
                    rating,

                "price":
                    device.price,

            },

            ###################################################
            # CLOSEST
            ###################################################

            "closest":
                None,

            ###################################################
            # MESSAGE
            ###################################################

            "message":
                None,

            ###################################################
            # WARNINGS
            ###################################################

            "warnings":
                warnings,
        }

    ###########################################################
    # CLOSEST AVAILABLE
    ###########################################################

    closest = None

    if closest_filters:

        closest = (

            model.objects

            .filter(

                active=True,

                **closest_filters

            )

            .order_by(

                f"-{order_field}"

            )

            .first()

        )

    ###########################################################
    # BUILD CLOSEST
    ###########################################################

    closest_data = None

    if closest:

        closest_data = {

            "object":
                closest,

            "name":
                str(closest),

            "manufacturer":
                getattr(
                    closest,
                    "manufacturer",
                    ""
                ),

            "rating":

                getattr(

                    closest,

                    "current_rating",

                    getattr(

                        closest,

                        "voltage_rating",

                        None

                    )

                ),

            "price":
                closest.price,

        }

    ###########################################################
    # FAILURE
    ###########################################################

    warnings.append(
        "Suitable protection device not found."
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

        "selected":
            None,

        ###################################################
        # CLOSEST
        ###################################################

        "closest":
            closest_data,

        ###################################################
        # MESSAGE
        ###################################################

        "message":
            "No suitable protection device found.",

        ###################################################
        # WARNINGS
        ###################################################

        "warnings":
            warnings,
    }


####################################################
# PV FUSE
####################################################

def pv_fuse(array_isc):

    required_current = array_isc * 1.25

    return _select_protection(

        Fuse,

        {
            "fuse_type": "pv",
            "current_rating__gte":
                required_current
        },

        "current_rating",

        {
            "current":
                round(
                    required_current,
                    2
                )
        },

        {
            "fuse_type": "pv"
        }
    )


####################################################
# BATTERY BREAKER
####################################################

def battery_breaker(
        inverter_power,
        battery_voltage,
        efficiency=0.90):

    current = (
        inverter_power
        /
        (
            battery_voltage
            *
            efficiency
        )
    ) * 1.25

    return _select_protection(

        Breaker,

        {
            "breaker_type": "dc",
            "current_rating__gte":
                current
        },

        "current_rating",

        {
            "current":
                round(
                    current,
                    2
                )
        },

        {
            "breaker_type": "dc"
        }
    )


####################################################
# AC BREAKER
####################################################

def ac_breaker(
        inverter_power,
        voltage=230):

    current = (
        inverter_power
        /
        voltage
    ) * 1.25

    return _select_protection(

        Breaker,

        {
            "breaker_type": "ac",
            "current_rating__gte":
                current
        },

        "current_rating",

        {
            "current":
                round(
                    current,
                    2
                )
        },

        {
            "breaker_type": "ac"
        }
    )


####################################################
# DC SPD
####################################################

def select_dc_spd(voc):

    required = voc * 1.2

    return _select_protection(

        SPD,

        {
            "spd_type": "dc",
            "voltage_rating__gte":
                required
        },

        "voltage_rating",

        {
            "voltage":
                round(
                    required,
                    2
                )
        },

        {
            "spd_type": "dc"
        }
    )


####################################################
# AC SPD
####################################################

def select_ac_spd():

    return _select_protection(

        SPD,

        {
            "spd_type": "ac"
        },

        "voltage_rating",

        {
            "voltage": 230
        },

        {
            "spd_type": "ac"
        }
    )


####################################################
# PV ISOLATOR
####################################################

def pv_isolator(
        current,
        voltage):

    current *= 1.25

    return _select_protection(

        Isolator,

        {
            "isolator_type": "dc",
            "current_rating__gte":
                current,
            "voltage_rating__gte":
                voltage
        },

        "current_rating",

        {
            "current":
                round(
                    current,
                    2
                ),
            "voltage":
                voltage
        },

        {
            "isolator_type": "dc"
        }
    )


####################################################
# AC ISOLATOR
####################################################

def ac_isolator(
        inverter_power,
        voltage=230):

    current = (
        inverter_power
        /
        voltage
    ) * 1.25

    return _select_protection(

        Isolator,

        {
            "isolator_type": "ac",
            "current_rating__gte":
                current
        },

        "current_rating",

        {
            "current":
                round(
                    current,
                    2
                )
        },

        {
            "isolator_type": "ac"
        }
    )