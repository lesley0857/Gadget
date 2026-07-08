# solar/services/accessories_engine.py

import math

from solar.models import Accessory


####################################################
# ACCESSORY LOOKUP
####################################################

def get_accessory(accessory_type):

    return (

        Accessory.objects

        .filter(

            active=True,

            accessory_type=accessory_type

        )

        .first()

    )


####################################################
# ADD ACCESSORY
####################################################

def _add_accessory(

        accessories,

        accessory_type,

        quantity):

    """
    Adds accessory if available.
    """

    accessory = get_accessory(
        accessory_type
    )

    if not accessory:

        return

    total = (

        quantity
        *
        accessory.price

    )

    accessories.append({

        "object":
            accessory,

        "name":
            accessory.name,

        "type":
            accessory.accessory_type,

        "quantity":
            quantity,

        "unit":
            accessory.unit,

        "unit_price":
            accessory.price,

        "total_price":
            total,
    })


####################################################
# BUILD ACCESSORIES
####################################################

def build_accessories(

        panel_quantity,

        battery_quantity,

        pv_distance,

        battery_distance,

        ac_distance):

    """
    Automatically generate project accessories.
    """

    accessories = []

    ################################################
    # PANEL CLAMPS
    ################################################

    _add_accessory(

        accessories,

        "clamp",

        panel_quantity * 4

    )

    ################################################
    # BOLTS
    ################################################

    _add_accessory(

        accessories,

        "bolt",

        panel_quantity * 8

    )

    ################################################
    # NUTS
    ################################################

    _add_accessory(

        accessories,

        "nut",

        panel_quantity * 8

    )

    ################################################
    # WASHERS
    ################################################

    _add_accessory(

        accessories,

        "washer",

        panel_quantity * 8

    )

    ################################################
    # MC4 CONNECTORS
    ################################################

    connector_qty = max(

        2,

        math.ceil(
            panel_quantity / 2
        )

    )

    _add_accessory(

        accessories,

        "connector",

        connector_qty

    )

    ################################################
    # CABLE GLANDS
    ################################################

    gland_qty = max(

        4,

        math.ceil(

            (

                pv_distance
                +
                battery_distance
                +
                ac_distance

            )

            / 10

        )

    )

    _add_accessory(

        accessories,

        "gland",

        gland_qty

    )

    ################################################
    # CABLE LUGS
    ################################################

    lug_qty = max(

        8,

        battery_quantity * 2

    )

    _add_accessory(

        accessories,

        "lug",

        lug_qty

    )

    ################################################
    # BATTERY RACK
    ################################################

    if battery_quantity > 2:

        rack_qty = math.ceil(

            battery_quantity
            /
            4

        )

        _add_accessory(

            accessories,

            "battery_rack",

            rack_qty

        )

    ################################################
    # SUMMARY
    ################################################

    total_cost = sum(

        item["total_price"]

        for item in accessories

    )

    ################################################
    # RETURN
    ################################################

    return {

        "success":

            True,

        "items":

            accessories,

        "summary": {

            "count":

                len(
                    accessories
                ),

            "total_cost":

                round(
                    total_cost,
                    2
                ),

        },

        "closest":

            None,

        "message":

            None,
    }