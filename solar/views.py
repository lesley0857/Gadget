import traceback

from django.shortcuts import render, redirect

from .forms import SolarCalculatorForm

from .models import (

    Appliance,
    DesignSetting,

)

from .services.load_engine import calculate_load

from .services.battery_engine import calculate_battery_bank

from .services.panel_engine import calculate_panels

from .services.inverter_engine import select_inverter

from .services.controller_engine import select_controller

from .services.cable_engine import (

    calculate_dc_cable,
    calculate_ac_cable,
    battery_cable,
    earth_cable,

)

from .services.protection_engine import (
    pv_fuse, ac_breaker, battery_breaker, select_ac_spd,
    select_dc_spd, pv_isolator,ac_isolator 
)

from .services.accessories_engine import (
    build_accessories
)

from .services.boq_engine import (
    generate_boq
)

from .services.pricing_engine import (
    calculate_pricing
)

from .services.warning_engine import (
    build_warnings
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

    except Exception:

        return data
    
###############################################################
# ADMIN LOADS
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

    for i, appliance_id in enumerate(appliance_ids):

        try:

            appliance = Appliance.objects.get(
                id=appliance_id
            )

        except Appliance.DoesNotExist:

            continue

        loads.append({

            "name":
                appliance.name,

            "watts":
                appliance.wattage,

            "qty":
                float(
                    quantities[i]
                ),

            "hours":
                float(
                    hours[i]
                ),

            "surge":
                appliance.surge_factor,

        })

    return loads

###############################################################
# CUSTOM LOADS
###############################################################

def build_custom_loads(request):

    loads = []

    names = request.POST.getlist(
        "custom_name"
    )

    watts = request.POST.getlist(
        "custom_watts"
    )

    qty = request.POST.getlist(
        "custom_qty"
    )

    hrs = request.POST.getlist(
        "custom_hours"
    )

    for i, name in enumerate(names):

        if not name:

            continue

        loads.append({

            "name":
                name,

            "watts":
                float(
                    watts[i]
                ),

            "qty":
                float(
                    qty[i]
                ),

            "hours":
                float(
                    hrs[i]
                ),

            "surge":
                1,

        })

    return loads

###############################################################
# BUILD LOAD LIST
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

    ###############################################################
    # INITIAL PAGE
    ###############################################################

    appliances = Appliance.objects.filter(popular=True)

    form = SolarCalculatorForm()

    if request.method != "POST":

        return render(

            request,

            "solar/calculator.html",

            {

                "form": form,

                "appliances": appliances,

            }

        )

    ###############################################################
    # VALIDATE FORM
    ###############################################################

    form = SolarCalculatorForm(request.POST)

    if not form.is_valid():

        return render(

            request,

            "solar/calculator.html",

            {

                "form": form,

                "appliances": appliances,

            }

        )

    try:

        ###########################################################
        # LOAD ENGINE
        ###########################################################

        loads = build_loads(request)

        load = calculate_load(loads)

        ###########################################################
        # DESIGN SETTINGS
        ###########################################################

        settings = DesignSetting.objects.first()

        if settings is None:

            raise Exception(

                "Design settings have not been configured."

            )

        ###########################################################
        # USER COMPONENTS
        ###########################################################

        battery = form.cleaned_data["battery"]

        panel = form.cleaned_data["panel"]

        autonomy = form.cleaned_data["autonomy"]

        peak_sun_hours = form.cleaned_data["peak_sun_hours"]

        ###########################################################
        # BATTERY ENGINE
        ###########################################################

        battery_result = calculate_battery_bank(

            load_watts=load["load_watts"],

            daily_energy=load["daily_energy_wh"],

            autonomy_days=autonomy,

            battery=battery,

            inverter_efficiency=battery.efficiency,

        )

                ###########################################################
        # PANEL ENGINE
        ###########################################################

        panel_result = calculate_panels(

            daily_energy=load["daily_energy_wh"],

            peak_sun_hours=peak_sun_hours,

            performance_ratio=settings.performance_ratio,

            panel=panel,

            battery_voltage=battery_result["required"]["system_voltage"],

            oversize_factor=settings.future_expansion,

        )

        print("\n===== PANEL RESULT =====")
        print(panel_result)
        print("========================\n")


        ###########################################################
        # INVERTER ENGINE
        ###########################################################

        inverter_result = select_inverter(

            running_load=load["load_watts"],

            surge_load=load["surge_watts"],

            battery_voltage=battery_result["required"]["system_voltage"]

        )

        if not inverter_result["success"]:

            inverter_result["message"] = (
                "No inverter currently exists in stock that satisfies "
                "the calculated engineering requirement. "
                "The required inverter specification is shown below and "
                "can be supplied on demand."
            )


        ###########################################################
        # CONTROLLER ENGINE
        ###########################################################

        controller_result = select_controller(

            battery_voltage=battery_result["required"]["system_voltage"],

            array_voltage=panel_result["selected"]["array_voltage"],

            array_current=panel_result["selected"]["array_current"],

            array_power=panel_result["selected"]["installed_power"],

        )

        if not controller_result["success"]:

            controller_result["message"] = (
                "No compatible charge controller is currently available. "
                "The required controller specification has been calculated "
                "and can be supplied on demand."
            )


        ###########################################################
        # SAFE VALUES
        ###########################################################

        selected_inverter = inverter_result.get("selected")
        required_inverter = inverter_result.get("required")

        selected_controller = controller_result.get("selected")
        required_controller = controller_result.get("required")


        ###########################################################
        # CABLE DESIGN
        ###########################################################

        pv_cable = calculate_dc_cable(

            current=panel_result["selected"]["array_current"],

            voltage=panel_result["selected"]["array_voltage"],

            distance=form.cleaned_data["pv_distance"],

        )


        ###########################################################
        # BATTERY CABLE
        ###########################################################

        battery_cable_result = battery_cable(

            inverter_power=(
                selected_inverter["rated_power"]
                if selected_inverter
                else required_inverter["continuous_power"]
            ),

            battery_voltage=battery_result["required"]["system_voltage"],

            distance=form.cleaned_data["battery_distance"],

        )


        ###########################################################
        # AC CABLE
        ###########################################################

        ac_cable = calculate_ac_cable(

            power=(
                selected_inverter["rated_power"]
                if selected_inverter
                else required_inverter["continuous_power"]
            ),

            voltage=230,

            distance=form.cleaned_data["ac_distance"],

        )


        ###########################################################
        # EARTH CABLE
        ###########################################################

        earth = earth_cable(

            phase_size=ac_cable["required"]["size"],

            distance=form.cleaned_data["ac_distance"],

        )

        print("\n========== CABLE DEBUG ==========")

        print(panel_result)

        print(inverter_result)

        print(controller_result)

        print(battery_result)

        print("================================\n")
        ###########################################################
        # SYSTEM VOLTAGE
        ###########################################################

        system_voltage = battery_result["required"]["system_voltage"]

        ###########################################################
        # PANEL ENGINE
        ###########################################################

        panel_result = calculate_panels(

            daily_energy=load["daily_energy_wh"],

            peak_sun_hours=peak_sun_hours,

            performance_ratio=settings.performance_ratio,

            panel=panel,

            battery_voltage=system_voltage,

            oversize_factor=settings.future_expansion,

        )

        ###########################################################
        # INVERTER ENGINE
        ###########################################################

        inverter_result = select_inverter(

            running_load=load["load_watts"],

            surge_load=load["surge_watts"],

            battery_voltage=system_voltage,

        )

        ###########################################################
        # CONTROLLER ENGINE
        ###########################################################

        controller_result = select_controller(

            battery_voltage=system_voltage,

            array_voltage=panel_result["required"]["array_voltage"],

            array_current=panel_result["required"]["array_current"],

            array_power=panel_result["required"]["installed_power"],

        )

        ###########################################################
        # ENGINEERING VALUES
        # (Used when products are unavailable)
        ###########################################################

        battery_quantity = battery_result["required"]["quantity"]

        panel_quantity = panel_result["required"]["quantity"]

        inverter_power = inverter_result["required"]["continuous_power"]

        array_voltage = panel_result["required"]["array_voltage"]

        array_current = panel_result["required"]["array_current"]

        array_power = panel_result["required"]["installed_power"]

        array_isc = panel_result["required"]["array_isc"]

        corrected_voc = panel_result["required"]["corrected_voc"]

        ###########################################################
        # DATABASE PRODUCTS (IF AVAILABLE)
        ###########################################################

        selected_battery = battery_result.get("selected")

        selected_panel = panel_result.get("selected")

        selected_inverter = inverter_result.get("selected")

        selected_controller = controller_result.get("selected")

        ###########################################################
        # OVERRIDE REQUIRED VALUES
        # WITH ACTUAL SELECTED PRODUCTS
        ###########################################################

        if selected_battery:

            battery_quantity = selected_battery["quantity"]

        if selected_panel:

            panel_quantity = selected_panel["quantity"]

            array_voltage = selected_panel["array_voltage"]

            array_current = selected_panel["array_current"]

            array_power = selected_panel["installed_power"]

            array_isc = selected_panel["array_isc"]

            corrected_voc = selected_panel["corrected_voc"]

        if selected_inverter:

            inverter_power = selected_inverter["rated_power"]

        ###########################################################
        # ENGINEERING VALIDATION
        ###########################################################

        engines = [

            battery_result,

            panel_result,

            inverter_result,

            controller_result,

            pv_cable,

            battery_cable_result,

            ac_cable,

            earth,

        ]

        ###########################################################
        # PROTECTION DEVICES
        ###########################################################

        protection = {

            "pv_fuse":

                pv_fuse(
                    panel_result["selected"]["array_isc"]
                ),

            "battery_breaker":

                battery_breaker(

                    selected_inverter["rated_power"]
                    if selected_inverter
                    else required_inverter["continuous_power"],

                    battery_result["required"]["system_voltage"],

                ),

            "ac_breaker":

                ac_breaker(

                    selected_inverter["rated_power"]
                    if selected_inverter
                    else required_inverter["continuous_power"]

                ),

            "dc_spd":

                select_dc_spd(

                    panel_result["selected"]["corrected_voc"]

                ),

            "ac_spd":

                select_ac_spd(),

            "pv_isolator":

                pv_isolator(

                    panel_result["selected"]["array_current"],

                    panel_result["selected"]["corrected_voc"],

                ),

            "ac_isolator":

                ac_isolator(

                    selected_inverter["rated_power"]
                    if selected_inverter
                    else required_inverter["continuous_power"]

                ),

        }

        ###########################################################
        # EQUIPMENT VALIDATION
        ###########################################################

        equipment = [

            pv_cable,

            battery_cable_result,

            ac_cable,

            earth,

            *protection.values(),

        ]

        engineering_messages = []

        for item in equipment:

            if not item["success"]:

                engineering_messages.append(item["message"])

        ###########################################################
        # ACCESSORIES
        ###########################################################

        accessories = build_accessories(

            panel_quantity=panel_result["selected"]["quantity"],

            battery_quantity=battery_result["selected"]["quantity"],

            pv_distance=form.cleaned_data["pv_distance"],

            battery_distance=form.cleaned_data["battery_distance"],

            ac_distance=form.cleaned_data["ac_distance"],

        )

        ###########################################################
        # BILL OF QUANTITIES
        ###########################################################

        boq = generate_boq(

            panel_count=panel_result["selected"]["quantity"],

            battery_count=battery_result["selected"]["quantity"],

            inverter_power=(

                selected_inverter["rated_power"]

                if selected_inverter

                else required_inverter["continuous_power"]

            ),

        )

        ###########################################################
        # PRICING
        ###########################################################

        pricing = calculate_pricing(

            battery=battery,

            battery_qty=battery_result["selected"]["quantity"],

            panel=panel,

            panel_qty=panel_result["selected"]["quantity"],

            inverter=inverter_result,

            controller=controller_result,

            settings=settings,

            cables=[

                pv_cable.get("selected"),

                battery_cable_result.get("selected"),

                ac_cable.get("selected"),

                earth.get("selected"),

            ],

            protections=list(protection.values()),

            accessories=accessories["items"],

            boq=boq["items"],

        )

        ###########################################################
        # RESULT
        ###########################################################

        result = {

            "load": load,

            "battery": battery_result,

            "panel": panel_result,

            "inverter": inverter_result,

            "controller": controller_result,

            "pv_cable": pv_cable,

            "battery_cable": battery_cable_result,

            "ac_cable": ac_cable,

            "earth_cable": earth,

            "protection": protection,

            "accessories": accessories,

            "boq": boq,

            "pricing": pricing,

            "loads": loads,

            "battery_name": str(battery),

            "panel_name": str(panel),

            "engineering_messages": engineering_messages,

        }

        ###########################################################
        # GLOBAL WARNINGS
        ###########################################################

        result["warnings"] = build_warnings(result)

        ###############################################################
        # RESULTS
        ###############################################################

        ###########################################################
        # SAVE RESULT
        ###########################################################

        request.session["solar_result"] = make_json_safe(result)

        ###########################################################
        # REDIRECT TO RESULT PAGE
        ###########################################################

        return redirect("result")

        ###############################################################
        # EXCEPTION
        ###############################################################

    except Exception as e:

        traceback.print_exc()

        return render(

            request,

            "solar/calculator.html",

            {

                    "form": form,

                    "appliances": appliances,

                    "error": (
                        "An unexpected error occurred while generating the "
                        "solar design. Please try again or contact support."
                    ),

                    # Optional: useful during development
                    "debug_error": str(e),

                },

            )


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

            "result": result,

        },

    )



###############################################################
# QUOTATION
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

            "result": result,

        },

    )