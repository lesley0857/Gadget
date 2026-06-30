from django.shortcuts import render
from .models import Appliance
import json


def solar_calculator(request):

    appliances = list(
        Appliance.objects.values(
            "id",
            "name",
            "wattage"
        )
    )

    return render(
        request,
        "calc.html",
        {
            "appliances_json": json.dumps(appliances)
        }
    )