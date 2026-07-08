# solar/services/boq_engine.py

from solar.models import BOQItem


####################################################
# ADD BOQ ITEM
####################################################

def _add_items(
        boq,
        queryset,
        quantity):

    """
    Add BOQ items from queryset.
    """

    for item in queryset:

        total = quantity * item.unit_price

        boq.append({

            "object":
                item,

            "description":
                item.description,

            "category":
                item.category,

            "unit":
                item.unit,

            "quantity":
                quantity,

            "unit_price":
                item.unit_price,

            "total_price":
                total,
        })


####################################################
# BUILD BOQ
####################################################

def generate_boq(

        panel_count,

        battery_count,

        inverter_power):

    """
    Generate engineering BOQ.
    """

    boq = []

    ################################################
    # LABOUR
    ################################################

    labour_qty = max(
        1,
        round(panel_count / 4)
    )

    labour = (

        BOQItem.objects

        .filter(

            active=True,

            category="labour"

        )

    )

    _add_items(

        boq,

        labour,

        labour_qty

    )

    ################################################
    # TRANSPORT
    ################################################

    transport = (

        BOQItem.objects

        .filter(

            active=True,

            category="transport"

        )

    )

    _add_items(

        boq,

        transport,

        1

    )

    ################################################
    # MATERIALS
    ################################################

    materials = (

        BOQItem.objects

        .filter(

            active=True,

            category="material"

        )

    )

    _add_items(

        boq,

        materials,

        1

    )

    ################################################
    # SUMMARY
    ################################################

    total_cost = sum(

        item["total_price"]

        for item in boq

    )

    ################################################
    # RETURN
    ################################################

    return {

        "success":

            True,

        "items":

            boq,

        "summary": {

            "count":

                len(
                    boq
                ),

            "total_cost":

                round(
                    total_cost,
                    2
                ),

            "panel_count":

                panel_count,

            "battery_count":

                battery_count,

            "inverter_power":

                inverter_power,

        },

        "closest":

            None,

        "message":

            None,
    }