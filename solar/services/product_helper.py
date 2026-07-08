def engineering_value(
        component,
        field):

    if component.get(
            "success"):

        return component[
            "selected"
        ][field]

    return component[
        "required"
    ][field]