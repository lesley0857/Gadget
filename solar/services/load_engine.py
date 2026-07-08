# solar/services/load_engine.py

def calculate_load(loads):

    total_running = 0
    total_energy = 0
    maximum_extra_surge = 0
    total_quantity = 0
    motor_load = 0
    resistive_load = 0

    schedule = []

    for item in loads:

        watts = float(item["watts"])
        qty = int(item["qty"])
        hours = float(item["hours"])
        surge = float(
            item.get(
                "surge",
                1
            )
        )

        running = watts * qty
        total_quantity += qty
        energy = running * hours

        surge_load = running * surge

        extra_surge = (

            surge_load
            -
            running
        )

        total_running += running

        total_energy += energy

        if surge > 1:

            motor_load += running

            maximum_extra_surge = max(
                maximum_extra_surge,
                extra_surge
            )

        else:

            resistive_load += running

        schedule.append({
            "name": item["name"],
            "watts": watts,
            "quantity": qty,
            "hours": hours,
            "running_load": running,
            "daily_energy": energy,
            "surge_factor": surge,
            "surge_load": surge_load,
        })

    total_surge = (

        total_running
        +
        maximum_extra_surge
    )
    diversity_factor = 1.0
    return {

        "load_watts":
            round(
                total_running,
                2
            ),

        "daily_energy_wh":
            round(
                total_energy,
                2
            ),

        "surge_watts":
            round(
                total_surge,
                2
            ),

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

        "largest_extra_surge":
            round(
                maximum_extra_surge,
                2
            ),
        "total_quantity": round(total_quantity,2),
        "diversity_factor": round(diversity_factor,2),
        "loads":
            schedule,
    }