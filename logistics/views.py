from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import timedelta, timezone

# Create your views here.
from orders.models import *
from .models import *

def track_shipment(request, tracking_id):

    shipment = Shipment.objects.select_related("order").get(
        tracking_id=tracking_id
    )

    return render(request, "tracking.html", {
        "shipment": shipment,
        "order": shipment.order
    })

@login_required
def delivery_dashboard(request):

    shipments = Shipment.objects.filter(
        delivery_agent_phone=request.userprofile.phone
    )

    return render(request, "delivery_dashboard.html", {
        "shipments": shipments
    })

@login_required
def update_shipment_status(request, shipment_id):

    shipment = Shipment.objects.get(id=shipment_id)

    shipment.status = request.POST.get("status")

    if shipment.status == "delivered":
        shipment.delivered_at = timezone.now()

    shipment.save()

    return redirect("delivery_dashboard")