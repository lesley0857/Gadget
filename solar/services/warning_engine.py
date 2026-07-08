def build_warnings(result):

    warnings = []

    checks = [

        ("inverter", "Inverter"),
        ("controller", "Charge Controller"),
        ("pv_cable", "PV Cable"),
        ("battery_cable", "Battery Cable"),
        ("ac_cable", "AC Cable"),
    ]

    for key, name in checks:

        item = result.get(key)

        if isinstance(item, dict):

            if not item.get("success", True):

                warnings.append(
                    f"{name} not found in database."
                )

    protection = result.get(
        "protection",
        {}
    )

    for key, value in protection.items():

        if isinstance(value, dict):

            if not value.get(
                "success",
                True
            ):

                warnings.append(
                    f"{key.replace('_',' ').title()} not found."
                )

    return warnings