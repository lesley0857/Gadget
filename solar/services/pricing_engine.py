from decimal import Decimal


def get_price(item):

    if not item:
        return Decimal("0")

    if item.get("success"):

        selected = item.get(
            "selected"
        )

        if selected:
            return Decimal(
                selected.get(
                    "price",
                    0
                )
            )

    closest = item.get(
        "closest"
    )

    if closest:
        return Decimal(
            closest.get(
                "price",
                0
            )
        )

    return Decimal("0")


def calculate_pricing(

        battery,
        battery_qty,

        panel,
        panel_qty,

        inverter,

        controller,

        settings,

        cables=None,

        protections=None,

        accessories=None,

        boq=None):

    cables = cables or []
    protections = protections or []
    accessories = accessories or []
    boq = boq or []

    ##################################################
    # CORE EQUIPMENT
    ##################################################

    battery_total = (
        Decimal(
            battery.price
        )
        *
        battery_qty
    )

    panel_total = (
        Decimal(
            panel.price
        )
        *
        panel_qty
    )

    inverter_total = get_price(
        inverter
    )

    controller_total = get_price(
        controller
    )

    ##################################################
    # CABLES
    ##################################################

    cable_total = sum(

        Decimal(
            c.get(
                "total_price",
                0
            )
        )

        for c in cables
        if c is not None
    )

    ##################################################
    # PROTECTION
    ##################################################

    protection_total = Decimal(
        "0"
    )

    for item in protections:
        if item is not None:
            protection_total += get_price(
                item
            )

    ##################################################
    # ACCESSORIES
    ##################################################

    accessory_total = sum(

        Decimal(
            a.get(
                "total_price",
                0
            )
        )

        for a in accessories
        if a is not None
    )

    ##################################################
    # BOQ
    ##################################################

    boq_total = sum(

        Decimal(
            b.get(
                "total_price",
                0
            )
        )

        for b in boq
        if b is not None
    )

    ##################################################
    # TOTAL MATERIALS
    ##################################################

    materials = (

        battery_total
        +
        panel_total
        +
        inverter_total
        +
        controller_total
        +
        cable_total
        +
        protection_total
        +
        accessory_total
        +
        boq_total
    )

    installation = (

        materials
        *
        Decimal(
            settings.installation_percentage
        )
        / 100
    )

    project_cost = (
        materials
        +
        installation
    )

    profit = (

        project_cost
        *
        Decimal(
            settings.profit_percentage
        )
        / 100
    )

    subtotal = (
        project_cost
        +
        profit
    )

    vat = (

        subtotal
        *
        Decimal(
            settings.vat_percentage
        )
        / 100
    )

    grand_total = (
        subtotal
        +
        vat
    )

    return {

        "materials":
            round(
                materials,
                2
            ),

        "installation":
            round(
                installation,
                2
            ),

        "project_cost":
            round(
                project_cost,
                2
            ),

        "profit":
            round(
                profit,
                2
            ),

        "vat":
            round(
                vat,
                2
            ),

        "grand_total":
            round(
                grand_total,
                2
            ),

        "battery_total":
            round(
                battery_total,
                2
            ),

        "panel_total":
            round(
                panel_total,
                2
            ),

        "inverter_total":
            round(
                inverter_total,
                2
            ),

        "controller_total":
            round(
                controller_total,
                2
            ),

        "cable_total":
            round(
                cable_total,
                2
            ),

        "protection_total":
            round(
                protection_total,
                2
            ),

        "accessory_total":
            round(
                accessory_total,
                2
            ),

        "boq_total":
            round(
                boq_total,
                2
            )
    }