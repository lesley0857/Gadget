# solar/services/system_voltage.py

###############################################################

# SYSTEM VOLTAGE ENGINE

###############################################################

def determine_system_voltage(load_result):
    """
    Select the recommended DC battery-system voltage.

    The Load Engine must provide:

        - Total running load
        - Motor load
        - Resistive load
        - Estimated surge load
        - Number of motors/compressors
        - Simultaneous motor-start risk

    The engine evaluates:

        1. Total running power
        2. Motor loading
        3. Starting/surge power
        4. Number of motors/compressors
        5. Simultaneous starting risk
        6. Estimated battery current

    The selected voltage is passed to the Battery Engine.

    Supported system voltages:

        24 V
        48 V
        96 V

    """

    ###############################################################
    # READ LOAD ENGINE RESULTS
    ###############################################################

    running_load = float(

        load_result.get(

            "load_watts",

            0

        )

        or 0

    )


    motor_load = float(

        load_result.get(

            "motor_load",

            0

        )

        or 0

    )


    resistive_load = float(

        load_result.get(

            "resistive_load",

            0

        )

        or 0

    )


    surge_load = float(

        load_result.get(

            "surge_watts",

            running_load

        )

        or running_load

    )


    motor_count = int(

        load_result.get(

            "motor_count",

            0

        )

        or 0

    )


    simultaneous_motor_start = bool(

        load_result.get(

            "simultaneous_motor_start",

            False

        )

    )


    ###############################################################
    # VALIDATE VALUES
    ###############################################################

    running_load = max(

        running_load,

        0

    )


    motor_load = max(

        motor_load,

        0

    )


    resistive_load = max(

        resistive_load,

        0

    )


    surge_load = max(

        surge_load,

        running_load

    )


    motor_count = max(

        motor_count,

        0

    )


    ###############################################################
    # MOTOR LOAD RATIO
    ###############################################################

    if running_load > 0:

        motor_ratio = (

            motor_load

            /

            running_load

        )

    else:

        motor_ratio = 0


    ###############################################################
    # BATTERY CURRENT ESTIMATION
    ###############################################################

    inverter_efficiency = 0.95


    current_24v = (

        surge_load

        /

        24

        /

        inverter_efficiency

    )


    current_48v = (

        surge_load

        /

        48

        /

        inverter_efficiency

    )


    current_96v = (

        surge_load

        /

        96

        /

        inverter_efficiency

    )


    ###############################################################
    # VOLTAGE SELECTION
    ###############################################################

    selected_voltage = 24


    reasons = []


    ###############################################################
    # 96 V SYSTEM
    ###############################################################

    """

    96 V is selected for very large systems where
    even a 48 V battery bank would produce excessive
    DC current.

    """

    if (

        running_load > 8000

        or

        surge_load > 12000

        or

        current_48v > 250

    ):

        selected_voltage = 96

        reasons.append(

            "The total power or surge demand would produce "
            "excessive battery current at 48 V."

        )


    ###############################################################
    # 48 V SYSTEM
    ###############################################################

    elif (

        running_load > 3000

        or

        surge_load > 6000

        or

        current_24v > 150

        or

        motor_count >= 3

        or

        (

            motor_count >= 2

            and

            motor_ratio >= 0.40

        )

        or

        simultaneous_motor_start

    ):

        selected_voltage = 48

        reasons.append(

            "The load requires a higher-voltage battery system "
            "to reduce DC current and improve motor-starting capability."

        )


    ###############################################################
    # 24 V SYSTEM
    ###############################################################

    else:

        selected_voltage = 24

        reasons.append(

            "The total load, surge demand, motor loading, "
            "and estimated battery current are within the "
            "recommended range for a 24 V system."

        )


    ###############################################################
    # ADDITIONAL PROFESSIONAL MOTOR CHECK
    ###############################################################

    """

    Multiple motor/compressor loads should not normally
    remain on a 24 V system when they represent a
    significant portion of the total load.

    """

    if (

        selected_voltage == 24

        and

        motor_count >= 2

        and

        motor_ratio >= 0.40

    ):

        selected_voltage = 48

        reasons.append(

            "Multiple motor/compressor loads represent a "
            "significant portion of the total load. "
            "A 48 V system is recommended."

        )


    ###############################################################
    # FINAL RESULT
    ###############################################################

    return {

        "success": True,

        "system_voltage": selected_voltage,

        "running_load": round(

            running_load,

            2

        ),

        "motor_load": round(

            motor_load,

            2

        ),

        "resistive_load": round(

            resistive_load,

            2

        ),

        "surge_load": round(

            surge_load,

            2

        ),

        "motor_count": motor_count,

        "motor_ratio": round(

            motor_ratio * 100,

            2

        ),

        "simultaneous_motor_start": (

            simultaneous_motor_start

        ),

        "battery_current": {

            "24V": round(

                current_24v,

                2

            ),

            "48V": round(

                current_48v,

                2

            ),

            "96V": round(

                current_96v,

                2

            ),

        },

        "reasons": reasons,

        "message": (

            f"{selected_voltage} V system selected."

        ),

    }

