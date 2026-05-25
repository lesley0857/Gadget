from django.shortcuts import render

# Create your views here.
from orders.models import *
from .models import *

def track_order(request, reference):
    order = Order.objects.get(reference=reference)
    shipments = Shipment.objects.filter(order=order)

    return render(request, "tracking.html", {
        "order": order,
        "shipments": shipments
    })