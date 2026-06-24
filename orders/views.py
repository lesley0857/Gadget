from django.shortcuts import render,redirect
import requests
import json
import uuid
from django.conf import settings
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from decimal import Decimal

from cart.utils import build_vendor_checkout

from django.http import JsonResponse
from .models import Order
from logistics.models import *


@login_required
def orders_page(request):

    orders = (
        Order.objects
        .select_related("customer")
        .prefetch_related(
            "items",
            "items__product_listing",
            "items__product_listing__media"
        )
        .filter(customer=request.user)
        .order_by("-created_at")
    )

    context = {
        "orders": orders
    }

    return render(request, "order.html", context)


# =========================
# ORDER DETAIL PAGE
# =========================
@login_required
def order_detail(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )

    order_items = order.items.all()

    context = {
        "order": order,
        "order_items": order_items
    }

    return render(request, "order_detail.html", context)

@login_required
def track_order(request, order_number):
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )

    status_steps = {
    "pending": 1,
    "processing": 2,
    "picked": 3,
    "in_transit": 4,
    "out_for_delivery": 5,
    "delivered": 6,
    }

    current_step = status_steps.get(
        order.status,
        1
    )

    shipment = Shipment.objects.filter(
        order=order
    ).first()

    return render(
        request,
        "track_order.html",
        {
            "order": order,
            "shipment": shipment,
            "current_step": current_step,
        }
    )



# =========================
# AJAX ORDERS JSON
# =========================
@login_required
def orders_json(request):

    orders = (
        Order.objects
        .filter(customer=request.user)
        .prefetch_related("items", "items__product_listing")
        .order_by("-created_at")
    )

    data = []

    for order in orders:

        items_data = []

        for item in order.items.all():

            listing = item.product_listing

            image = ""

            if listing.media.exists():
                image = listing.media.first().file.url

            items_data.append({
                "id": item.id,
                "name": listing.product.name,
                "price": float(item.price),
                "quantity": item.quantity,
                "subtotal": float(item.price * item.quantity),
                "image": image,
                "status": order.status,
            })

        data.append({
            "order_id": order.id,
            "status": order.status,
            "total": float(order.total_amount),
            "created_at": order.created_at.strftime("%d %b %Y"),
            "items": items_data
        })

    return JsonResponse({
        "orders": data
    })