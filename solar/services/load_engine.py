# solar/services/load_engine.py

###############################################################

# LOAD ENGINE

###############################################################

def calculate_load(loads):
    """
    Solar Load Analysis Engine

    The load engine analyzes the electrical characteristics
    of all selected appliances.

    It does NOT select the system voltage.

    It calculates:

        1. Total running load
        2. Daily energy consumption
        3. Motor/compressor load
        4. Resistive load
        5. Surge load
        6. Number of motors/compressors
        7. Simultaneous motor-start risk
        8. Simultaneous starting load
        9. Largest individual surge
        10. Average load
        11. Appliance breakdown

    Expected input:

        {
            "name": "Frozen Food Freezer",
            "watts": 500,
            "qty": 2,
            "hours": 8,
            "surge": 3,
            "load_type": "compressor",
            "starting_type": "possible",
        }

    The system-voltage engine later uses these results to
    select 24 V, 48 V, or 96 V.
    """


    ###########################################################
    # TOTALS
    ###########################################################

    total_running = 0

    total_energy = 0

    total_quantity = 0

    motor_load = 0

    resistive_load = 0

    total_motors = 0

    largest_extra_surge = 0

    simultaneous_start_load = 0

    possible_simultaneous_start_load = 0

    simultaneous_motor_start = False


    ###########################################################
    # APPLIANCE BREAKDOWN
    ###########################################################

    schedule = []


    ###########################################################
    # EMPTY LOAD VALIDATION
    ###########################################################

    if not loads:

        return {

            "load_watts": 0,

            "daily_energy_wh": 0,

            "surge_watts": 0,

            "motor_load": 0,

            "resistive_load": 0,

            "total_motors": 0,

            "motor_count": 0,

            "simultaneous_start_load": 0,

            "possible_simultaneous_start_load": 0,

            "simultaneous_motor_start": False,

            "largest_extra_surge": 0,

            "total_quantity": 0,

            "diversity_factor": 1.0,

            "average_load_watts": 0,

            "peak_energy_hour": 0,

            "loads": [],

        }


    ###########################################################
    # PROCESS EACH APPLIANCE
    ###########################################################

    for item in loads:


        #######################################################
        # BASIC VALUES
        #######################################################

        name = (

            item.get(

                "name",

                "Unnamed Appliance"

            )

            or

            "Unnamed Appliance"

        )


        try:

            watts = float(

                item.get(

                    "watts",

                    0

                )

            )

        except (

            TypeError,

            ValueError,

        ):

            watts = 0


        try:

            quantity = int(

                float(

                    item.get(

                        "qty",

                        1

                    )

                )

            )

        except (

            TypeError,

            ValueError,

        ):

            quantity = 1


        try:

            hours = float(

                item.get(

                    "hours",

                    0

                )

            )

        except (

            TypeError,

            ValueError,

        ):

            hours = 0


        try:

            surge_factor = float(

                item.get(

                    "surge",

                    1

                )

            )

        except (

            TypeError,

            ValueError,

        ):

            surge_factor = 1


        #######################################################
        # LOAD TYPE
        #######################################################

        load_type = (

            item.get(

                "load_type",

                "resistive"

            )

            or

            "resistive"

        ).lower()


        #######################################################
        # STARTING TYPE
        #######################################################

        starting_type = (

            item.get(

                "starting_type",

                "single"

            )

            or

            "single"

        ).lower()


        #######################################################
        # SANITIZE VALUES
        #######################################################

        watts = max(

            watts,

            0

        )


        quantity = max(

            quantity,

            0

        )


        hours = max(

            min(

                hours,

                24

            ),

            0

        )


        surge_factor = max(

            surge_factor,

            1

        )


        #######################################################
        # RUNNING LOAD
        #######################################################

        running_load = (

            watts

            *

            quantity

        )


        #######################################################
        # DAILY ENERGY
        #######################################################

        daily_energy = (

            running_load

            *

            hours

        )


        #######################################################
        # MAXIMUM SURGE
        #######################################################

        surge_load = (

            running_load

            *

            surge_factor

        )


        #######################################################
        # ADDITIONAL SURGE
        #######################################################

        extra_surge = (

            surge_load

            -

            running_load

        )


        #######################################################
        # TOTAL RUNNING LOAD
        #######################################################

        total_running += running_load


        #######################################################
        # TOTAL DAILY ENERGY
        #######################################################

        total_energy += daily_energy


        #######################################################
        # TOTAL QUANTITY
        #######################################################

        total_quantity += quantity


        #######################################################
        # LOAD CLASSIFICATION
        #######################################################

        is_motor_load = load_type in (

            "motor",

            "compressor",

        )


        if is_motor_load:

            motor_load += running_load


            total_motors += quantity


        else:

            resistive_load += running_load


        #######################################################
        # MOTOR STARTING RISK
        #######################################################

        if is_motor_load:


            if starting_type == "simultaneous":

                simultaneous_motor_start = True


                simultaneous_start_load += (

                    surge_load

                )


            elif starting_type == "possible":

                possible_simultaneous_start_load += (

                    surge_load

                )


        #######################################################
        # LARGEST INDIVIDUAL SURGE
        #######################################################

        largest_extra_surge = max(

            largest_extra_surge,

            extra_surge

        )


        #######################################################
        # APPLIANCE BREAKDOWN
        #######################################################

        schedule.append({

            "name":

                name,


            "watts":

                round(

                    watts,

                    2

                ),


            "quantity":

                quantity,


            "hours":

                round(

                    hours,

                    2

                ),


            "load_type":

                load_type,


            "starting_type":

                starting_type,


            "running_load":

                round(

                    running_load,

                    2

                ),


            "daily_energy":

                round(

                    daily_energy,

                    2

                ),


            "surge_factor":

                round(

                    surge_factor,

                    2

                ),


            "surge_load":

                round(

                    surge_load,

                    2

                ),


            "extra_surge":

                round(

                    extra_surge,

                    2

                ),

        })


    ###########################################################
    # TOTAL SURGE CALCULATION
    ###########################################################

    """

    If motors can definitely start together:

        Total surge
        =
        Full simultaneous motor surge
        +
        Other running loads

    If simultaneous starting is only possible:

        The possible simultaneous surge is used as
        an additional design risk.

    Otherwise:

        Total running load
        +
        Largest additional surge

    """


    if simultaneous_motor_start:


        total_surge = max(

            total_running

            +

            largest_extra_surge,


            simultaneous_start_load

            +

            (

                total_running

                -

                motor_load

            )

        )


    elif possible_simultaneous_start_load > 0:


        total_surge = max(

            total_running

            +

            largest_extra_surge,


            possible_simultaneous_start_load

            +

            (

                total_running

                -

                motor_load

            )

        )


    else:


        total_surge = (

            total_running

            +

            largest_extra_surge

        )


    ###########################################################
    # AVERAGE DAILY LOAD
    ###########################################################

    average_load = (

        total_energy

        /

        24

    )


    ###########################################################
    # PEAK ENERGY LOAD
    ###########################################################

    peak_energy_hour = 0


    if schedule:

        peak_energy_hour = max(

            item[

                "daily_energy"

            ]

            for item in schedule

        )


    ###########################################################
    # DIVERSITY FACTOR
    ###########################################################

    diversity_factor = 1.0


    ###########################################################
    # FINAL RESULT
    ###########################################################

    return {

        #######################################################
        # POWER
        #######################################################

        "load_watts":

            round(

                total_running,

                2

            ),


        #######################################################
        # ENERGY
        #######################################################

        "daily_energy_wh":

            round(

                total_energy,

                2

            ),


        #######################################################
        # SURGE
        #######################################################

        "surge_watts":

            round(

                total_surge,

                2

            ),


        #######################################################
        # LOAD CLASSIFICATION
        #######################################################

        "motor_load":

            round(

                motor_load,

                2

            ),


        "resistive_load":

            round(

                resistive_load,

                2

            ),


        #######################################################
        # MOTOR INFORMATION
        #######################################################

        "total_motors":

            total_motors,


        "motor_count":

            total_motors,


        "simultaneous_start_load":

            round(

                simultaneous_start_load,

                2

            ),


        "possible_simultaneous_start_load":

            round(

                possible_simultaneous_start_load,

                2

            ),


        "simultaneous_motor_start":

            simultaneous_motor_start,


        "largest_extra_surge":

            round(

                largest_extra_surge,

                2

            ),


        #######################################################
        # GENERAL INFORMATION
        #######################################################

        "total_quantity":

            total_quantity,


        "diversity_factor":

            diversity_factor,


        "average_load_watts":

            round(

                average_load,

                2

            ),


        "peak_energy_hour":

            round(

                peak_energy_hour,

                2

            ),


        #######################################################
        # APPLIANCE BREAKDOWN
        #######################################################

        "loads":

            schedule,

    }

