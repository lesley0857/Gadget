from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.utils import timezone
# Create your views here.
from orders.models import *
from .models import *
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from cart.utils import build_vendor_checkout
from .utils import serialize_decimals,send_shipping_negotiation_email,build_shipping_whatsapp_url
from logistics.models import Shipment


@login_required
def track_order(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )

    shipment = Shipment.objects.filter(
        order=order
    ).first()

    status_steps = {
        "pending": 1,
        "confirmed": 2,
        "processing": 2,
        "picked": 3,
        "in_transit": 3,
        "at_hub": 3,
        "shipped": 3,
        "out_for_delivery": 4,
        "delivered": 5,
    }

    current_step = status_steps.get(
        order.status,
        1
    )

    if shipment:
        current_step = status_steps.get(
            shipment.status,
            current_step
        )
        
    return render(
        request,
        "track_order.html",
        {
            "order": order,
            "shipment": shipment,
            "current_step": current_step,
        }
    )


@login_required
def delivery_dashboard(request):

    phone = (
        request.user.userprofile.phone
        if hasattr(request.user, "userprofile")
        else None
    )

    shipments = Shipment.objects.filter(
        delivery_agent_phone=phone
    ).order_by("-created_at")

    return render(
        request,
        "delivery_dashboard.html",
        {
            "shipments": shipments
        }
    )

from django.contrib import messages
from django.utils import timezone

@login_required
def update_shipment_status(request, shipment_id):

    shipment = get_object_or_404(
        Shipment,
        id=shipment_id
    )

    if request.method == "POST":

        shipment.status = request.POST.get(
            "status"
        )

        shipment.last_update = timezone.now()

        if shipment.status == "delivered":

            shipment.delivered_at = timezone.now()

            shipment.order.status = "delivered"
            shipment.order.save()

        elif shipment.status == "out_for_delivery":

            shipment.order.status = "out_for_delivery"
            shipment.order.save()

        elif shipment.status in [
            "picked",
            "in_transit",
            "at_hub"
        ]:

            shipment.order.status = "shipped"
            shipment.order.save()

        shipment.save()

        messages.success(
            request,
            "Shipment updated successfully."
        )

    return redirect(
        "delivery_dashboard"
    )







