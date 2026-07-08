# solar/services/market_selection_engine.py

from decimal import Decimal


def select_market_item(
        queryset,
        quantity=1,
        **requirements):
    """
    Generic market selector.

    Example:

    select_market_item(
        Cable.objects.filter(
            cable_type='pv'
        ),
        size_mm__gte=6,
        ampacity__gte=32
    )
    """

    #################################################
    # FILTER
    #################################################

    items = (
        queryset
        .filter(
            active=True,
            **requirements
        )
        .order_by(
            "price"
        )
    )

    item = items.first()

    #################################################
    # NOT FOUND
    #################################################

    if not item:

        return {

            "success": False,

            "error":
                (
                    "No market item found."
                ),

            "requirements":
                requirements
        }

    #################################################
    # PRICE
    #################################################

    if hasattr(item, "price"):

        unit_price = item.price

    elif hasattr(item, "price_per_meter"):

        unit_price = item.price_per_meter

    elif hasattr(item, "unit_price"):

        unit_price = item.unit_price

    else:

        unit_price = Decimal("0")

    #################################################
    # RETURN
    #################################################

    return {

        "success": True,

        "object":
            item,

        "name":
            str(item),

        "quantity":
            quantity,

        "unit_price":
            float(unit_price),

        "total_price":
            float(
                unit_price
                *
                quantity
            ),
    }