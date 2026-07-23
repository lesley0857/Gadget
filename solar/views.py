# solar/views.py

import traceback

from django.shortcuts import render, redirect

from .forms import SolarCalculatorForm

from .models import (Appliance,
DesignSetting,
)

from .services.load_engine import (
calculate_load,
)

from .services.system_voltage_engine import (
determine_system_voltage,
)

from .services.battery_engine import (
calculate_battery_bank,
)

from .services.panel_engine import (
calculate_panels,
)

from .services.inverter_engine import (
select_inverter,
)

from .services.controller_engine import (
select_controller,
)

from .services.cable_engine import (
calculate_dc_cable,
calculate_ac_cable,
battery_cable,
earth_cable,
)

from .services.protection_engine import (
pv_fuse,
ac_breaker,
battery_breaker,
select_ac_spd,
select_dc_spd,
pv_isolator,
ac_isolator,
)

from .services.accessories_engine import (
build_accessories,
)

from .services.boq_engine import (
generate_boq,
)

from .services.pricing_engine import (
calculate_pricing,
)

from .services.warning_engine import (
build_warnings,
)

###############################################################

# JSON SAFE CONVERTER

###############################################################

def make_json_safe(data):
    if isinstance(data, dict):

        return {

            key: make_json_safe(value)

            for key, value in data.items()

        }


    if isinstance(data, list):

        return [

            make_json_safe(item)

            for item in data

        ]


    if hasattr(data, "_meta"):

        return str(data)


    try:

        return float(data)

    except (

        TypeError,

        ValueError,

    ):

        return data

###############################################################

# BUILD ADMIN LOADS

###############################################################

def build_admin_loads(request):

    loads = []


    appliance_ids = request.POST.getlist(
        "appliance_id"
    )

    quantities = request.POST.getlist(
        "quantity"
    )

    hours = request.POST.getlist(
        "hours"
    )


    for index, appliance_id in enumerate(
        appliance_ids
    ):


        try:

            appliance = Appliance.objects.get(
                id=appliance_id
            )

        except Appliance.DoesNotExist:

            continue


        try:

            quantity = float(
                quantities[index]
            )

        except (

            IndexError,

            TypeError,

            ValueError,

        ):

            quantity = 1


        try:

            operating_hours = float(
                hours[index]
            )

        except (

            IndexError,

            TypeError,

            ValueError,

        ):

            operating_hours = 0


        loads.append({

            "name":
                appliance.name,

            "watts":
                appliance.wattage,

            "qty":
                quantity,

            "hours":
                operating_hours,

            "surge":
                appliance.surge_factor,
            "load_type": appliance.load_type,

            "starting_type": appliance.starting_type,
        })


    return loads



###############################################################

# BUILD CUSTOM LOADS

###############################################################
def build_custom_loads(request):

    loads = []


    names = request.POST.getlist(
        "custom_name"
    )

    watts = request.POST.getlist(
        "custom_watts"
    )

    quantities = request.POST.getlist(
        "custom_qty"
    )

    hours = request.POST.getlist(
        "custom_hours"
    )

    surge_factors = request.POST.getlist(
        "custom_surge"
    )

    load_types = request.POST.getlist(
        "custom_load_type"
    )

    starting_types = request.POST.getlist(
        "custom_starting_type"
    )


    for index, name in enumerate(names):


        if not name.strip():

            continue


        #######################################################
        # BASIC VALUES
        #######################################################

        try:

            wattage = float(

                watts[index]

            )

            quantity = float(

                quantities[index]

            )

            operating_hours = float(

                hours[index]

            )

        except (

            IndexError,

            TypeError,

            ValueError,

        ):

            continue


        #######################################################
        # SURGE FACTOR
        #######################################################

        try:

            surge_factor = float(

                surge_factors[index]

            )

        except (

            IndexError,

            TypeError,

            ValueError,

        ):

            surge_factor = 1


        #######################################################
        # LOAD TYPE
        #######################################################

        try:

            load_type = (

                load_types[index]

                or

                "resistive"

            ).lower()

        except IndexError:

            load_type = "resistive"


        #######################################################
        # STARTING TYPE
        #######################################################

        try:

            starting_type = (

                starting_types[index]

                or

                "single"

            ).lower()

        except IndexError:

            starting_type = "single"


        #######################################################
        # STORE LOAD
        #######################################################

        loads.append({

            "name":

                name.strip(),

            "watts":

                wattage,

            "qty":

                quantity,

            "hours":

                operating_hours,

            "surge":

                surge_factor,

            "load_type":

                load_type,

            "starting_type":

                starting_type,

        })


    return loads

###############################################################

# BUILD COMPLETE LOAD LIST

###############################################################

def build_loads(request):
    loads = []


    loads.extend(

        build_admin_loads(
            request
        )

    )


    loads.extend(

        build_custom_loads(
            request
        )

    )


    return loads


    ###############################################################

    # SOLAR CALCULATOR

    ###############################################################

def solar_calculator(request):


    appliances = Appliance.objects.filter(
        popular=True
    )


    form = SolarCalculatorForm()


    if request.method != "POST":

        return render(

            request,

            "solar/calculator.html",

            {

                "form":
                    form,

                "appliances":
                    appliances,

            }

        )


    form = SolarCalculatorForm(
        request.POST
    )


    if not form.is_valid():

        return render(

            request,

            "solar/calculator.html",

            {

                "form":
                    form,

                "appliances":
                    appliances,

            }

        )


    try:


        #######################################################
        # LOAD ENGINE
        #######################################################


        loads = build_loads(
            request
        )

        print("\n========== INPUT LOADS ==========")
        print(loads)
        print("=================================\n")


        if not loads:

            raise ValueError(

                "At least one appliance or custom load "
                "is required."

            )


        load_result = calculate_load(
            loads
        )

        print("\n========== LOAD ENGINE RESULT ==========")
        print(load_result)
        print("========================================\n")


        #######################################################
        # DESIGN SETTINGS
        #######################################################


        settings = DesignSetting.objects.first()


        if settings is None:

            raise ValueError(

                "Design settings have not been configured."

            )


        #######################################################
        # USER INPUTS
        #######################################################


        battery = form.cleaned_data.get(
            "battery"
        )


        panel = form.cleaned_data.get(
            "panel"
        )


        peak_sun_hours = form.cleaned_data.get(
            "peak_sun_hours"
        )


        operating_mode = form.cleaned_data.get(

            "operating_mode",

            "off_grid"

        )


        #######################################################
        # SYSTEM VOLTAGE ENGINE
        #######################################################


        system_voltage_result = determine_system_voltage(
            load_result
        )


        if not system_voltage_result.get(
            "success"
        ):

            raise ValueError(

                system_voltage_result.get(

                    "message",

                    "System voltage selection failed."

                )

            )


        system_voltage = (

            system_voltage_result.get(

                "system_voltage"

        )

    )
        
        if not system_voltage:

            raise ValueError(

                "System voltage could not be determined."

            )


        #######################################################
        # BATTERY ENGINE
        #######################################################


        battery_result = calculate_battery_bank(

            load_watts=load_result.get(

                "load_watts",

                0

            ),

            daily_energy=load_result.get(

                "daily_energy_wh",

                0

            ),

            battery=battery,

            system_voltage=system_voltage,

            inverter_efficiency=(

                battery.efficiency

                if battery

                else 0.95

            ),

            operating_mode=operating_mode,

        )


        if not battery_result.get(
            "success"
        ):

            raise ValueError(

                battery_result.get(

                    "message",

                    "Battery design failed."

                )

            )


        #######################################################
        # PANEL ENGINE
        #######################################################


        panel_result = calculate_panels(

            daily_energy=load_result.get(

                "daily_energy_wh",

                0

            ),

            peak_sun_hours=peak_sun_hours,

            performance_ratio=(

                settings.performance_ratio

            ),

            panel=panel,

            battery_voltage=system_voltage,

            oversize_factor=(

                settings.future_expansion

            ),

        )


        if not panel_result.get(
            "success"
        ):

            raise ValueError(

                panel_result.get(

                    "message",

                    "Solar panel design failed."

                )

            )


        #######################################################
        # PANEL VALUES
        #######################################################


        panel_data = panel_result.get(
            "selected"
        )


        panel_required = panel_result.get(

            "required",

            {}

        )


        panel_source = (

            panel_data

            if panel_data

            else panel_required

        )


        panel_quantity = panel_source.get(

            "quantity",

            0

        )


        array_voltage = panel_source.get(

            "array_voltage",

            0

        )


        array_current = panel_source.get(

            "array_current",

            0

        )


        array_power = panel_source.get(

            "installed_power",

            0

        )


        array_isc = panel_source.get(

            "array_isc",

            0

        )


        corrected_voc = panel_source.get(

            "corrected_voc",

            0

        )


        #######################################################
        # INVERTER ENGINE
        #######################################################


        inverter_result = select_inverter(

            running_load=load_result.get(

                "load_watts",

                0

            ),

            surge_load=load_result.get(

                "surge_watts",

                0

            ),

            battery_voltage=system_voltage,

        )


        if not inverter_result.get(
            "success"
        ):

            inverter_result["message"] = (

                "No inverter currently exists in stock "
                "that satisfies the calculated engineering "
                "requirements. The required specification "
                "is shown below."

            )


        #######################################################
        # INVERTER POWER
        #######################################################


        inverter_required = inverter_result.get(

            "required",

            {}

        )


        inverter_selected = inverter_result.get(

            "selected"

        )


        inverter_power = inverter_required.get(

            "continuous_power",

            0

        )


        if inverter_selected:

            inverter_power = inverter_selected.get(

                "rated_power",

                inverter_power

            )


        #######################################################
        # CONTROLLER ENGINE
        #######################################################


        controller_result = select_controller(

            battery_voltage=system_voltage,

            array_voltage=array_voltage,

            array_current=array_current,

            array_power=array_power,

        )


        if not controller_result.get(
            "success"
        ):

            controller_result["message"] = (

                "No compatible charge controller is "
                "currently available. The required "
                "specification is shown below."

            )


        #######################################################
        # CABLE DESIGN
        #######################################################


        pv_cable = calculate_dc_cable(

            current=array_current,

            voltage=array_voltage,

            distance=form.cleaned_data[
                "pv_distance"
            ],

        )


        battery_cable_result = battery_cable(

            inverter_power=inverter_power,

            battery_voltage=system_voltage,

            distance=form.cleaned_data[
                "battery_distance"
            ],

        )


        ac_cable = calculate_ac_cable(

            power=inverter_power,

            voltage=230,

            distance=form.cleaned_data[
                "ac_distance"
            ],

        )


        earth = earth_cable(

            phase_size=ac_cable[

                "required"

            ][

                "size"

            ],

            distance=form.cleaned_data[

                "ac_distance"

            ],

        )


        #######################################################
        # PROTECTION DEVICES
        #######################################################


        protection = {


            "pv_fuse": pv_fuse(

                array_isc

            ),


            "battery_breaker": battery_breaker(

                inverter_power,

                system_voltage,

            ),


            "ac_breaker": ac_breaker(

                inverter_power

            ),


            "dc_spd": select_dc_spd(

                corrected_voc

            ),


            "ac_spd": select_ac_spd(),


            "pv_isolator": pv_isolator(

                array_current,

                corrected_voc,

            ),


            "ac_isolator": ac_isolator(

                inverter_power

            ),

        }


        #######################################################
        # ENGINEERING VALIDATION
        #######################################################


        engineering_messages = []


        engines = [

            battery_result,

            panel_result,

            inverter_result,

            controller_result,

            pv_cable,

            battery_cable_result,

            ac_cable,

            earth,

            *protection.values(),

        ]


        for engine in engines:


            if not engine:

                continue


            if not engine.get(

                "success",

                True

            ):

                engineering_messages.append(

                    engine.get(

                        "message",

                        "Engineering calculation failed."

                    )

                )


        #######################################################
        # ACCESSORIES
        #######################################################


        selected_battery = battery_result.get(

            "selected"

        )


        battery_quantity = (

            selected_battery.get(

                "quantity",

                0

            )

            if selected_battery

            else battery_result.get(

                "required",

                {}

            ).get(

                "quantity",

                0

            )

        )


        accessories = build_accessories(

            panel_quantity=panel_quantity,

            battery_quantity=battery_quantity,

            pv_distance=form.cleaned_data[

                "pv_distance"

            ],

            battery_distance=form.cleaned_data[

                "battery_distance"

            ],

            ac_distance=form.cleaned_data[

                "ac_distance"

            ],

        )


        #######################################################
        # BILL OF QUANTITIES
        #######################################################


        boq = generate_boq(

            panel_count=panel_quantity,

            battery_count=battery_quantity,

            inverter_power=inverter_power,

        )


        #######################################################
        # PRICING
        #######################################################


        pricing = calculate_pricing(

            battery=battery,

            battery_qty=battery_quantity,

            panel=panel,

            panel_qty=panel_quantity,

            inverter=inverter_result,

            controller=controller_result,

            settings=settings,

            cables=[

                pv_cable.get(

                    "selected"

                ),

                battery_cable_result.get(

                    "selected"

                ),

                ac_cable.get(

                    "selected"

                ),

                earth.get(

                    "selected"

                ),

            ],

            protections=list(

                protection.values()

            ),

            accessories=accessories.get(

                "items",

                []

            ),

            boq=boq.get(

                "items",

                []

            ),

        )


        #######################################################
        # FINAL RESULT
        #######################################################


        result = {


            "load":

                load_result,


            "system_voltage":

                system_voltage_result,


            "battery":

                battery_result,


            "panel":

                panel_result,


            "inverter":

                inverter_result,


            "controller":

                controller_result,


            "pv_cable":

                pv_cable,


            "battery_cable":

                battery_cable_result,


            "ac_cable":

                ac_cable,


            "earth_cable":

                earth,


            "protection":

                protection,


            "accessories":

                accessories,


            "boq":

                boq,


            "pricing":

                pricing,


            "loads":

                loads,


            "battery_name":

                str(battery)

                if battery

                else "",


            "panel_name":

                str(panel)

                if panel

                else "",


            "system_voltage_value":

                system_voltage,


            "engineering_messages":

                engineering_messages,

        }


        #######################################################
        # GLOBAL WARNINGS
        #######################################################


        result["warnings"] = build_warnings(

            result

        )


        #######################################################
        # SAVE SESSION
        #######################################################


        request.session[

            "solar_result"

        ] = make_json_safe(

            result

        )


        return redirect(

            "result"

        )


    except Exception as error:


        traceback.print_exc()


        return render(

            request,

            "solar/calculator.html",

            {

                "form":

                    form,

                "appliances":

                    appliances,

                "error":

                    (

                        "An unexpected error occurred while "
                        "generating the solar design. "
                        "Please try again."

                    ),

                "debug_error":

                    str(error),

            }

        )



###############################################################

# SOLAR RESULT

###############################################################

def solar_result(request):

    result = request.session.get(

        "solar_result"

    )


    if not result:

        return redirect(

            "solar_calculator"

        )


    return render(

        request,

        "solar/results.html",

        {

            "result":

                result,

        }

    )


###############################################################

# SOLAR QUOTATION

###############################################################

def solar_quotation(request):

    result = request.session.get(

        "solar_result"

    )


    if not result:

        return redirect(

            "solar_calculator"

        )


    return render(

        request,

        "solar/quotation.html",

        {

            "result":

                result,

        }

    )

