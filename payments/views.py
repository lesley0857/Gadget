from django.shortcuts import render, redirect
import json
# Create your views here.
import requests
import uuid
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from decimal import Decimal
from orders.models import *
from django.http import JsonResponse
from cart.models import *

from logistics.models import Shipment, ShippingOption
from logistics.services.gigl import GIGLProvider
from logistics.services.aggregator import LogisticsAggregator
from cart.utils import *
from collections import defaultdict
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from wallets.models import VendorWallet, WalletTransaction, Commission
from logistics.services.router import *


def initiate_payment(request):

    user = request.user
    selected_shipping = request.POST.get("shipping_global")
    shipping_choice = request.POST.get("shipping_option")
    data = build_vendor_checkout(user, shipping_choice=shipping_choice)
    required_fields = ["address", "city", "state", "phone"]

    for field in required_fields:
        if not request.POST.get(field):
            return JsonResponse({"error": f"{field} is required"}, status=400)

    Order.objects.filter(
        customer=user,
        status="processing"
    ).update(status="cancelled")

    shipping_global = request.POST.get("shipping_global")
    shipping_id = request.POST.get("shipping_global")
    selected_shipping_option = None

    for v in data["vendors_data"]:
        for opt in data["shipping_options"]:
            if str(opt["id"]) == str(shipping_id):
                selected_shipping_option = opt
                break

    vendors = Vendor.objects.filter(
        id__in=[v["vendor_id"] for v in data["vendors_data"]],
        hub__isnull=True
    )

    if vendors.exists():
        return JsonResponse({
            "error": "Some vendors are not properly configured"
        })

    total = Decimal(data["total"])
    reference = str(uuid.uuid4())
    
    order = Order.objects.create(
        customer=user,
        total_amount=total,
        shipping_city=request.POST.get("city"),
        shipping_amount=data["shipping"],
        vat_amount=data["vat"],
        subtotal=data["subtotal"],
        reference=reference,
        status="processing",

        # ✅ SAVE USER DATA
        first_name=request.POST.get("first_name"),
        last_name=request.POST.get("last_name"),
        email=request.POST.get("email"),
        phone=request.POST.get("phone"),

        billing_address=request.POST.get("address"),
        shipping_address=request.POST.get("shipping_address") or request.POST.get("address"),

        locked_data=json.dumps(data)
    )

    res = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": user.email,
            "amount": int(total * 100),
            "reference": reference,
            "callback_url": "http://127.0.0.1:8000/payment/verify/"
        },
        headers={
            "Authorization": "Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    ).json()

    order.shipping_address = request.POST.get("shipping_address") or request.POST.get("address")
    order.save()
    if not res.get("status"):
        order.status = "cancelled"
        order.save()
        return JsonResponse({"error": res.get("message")}, status=400)

    order.payment_url = res["data"]["authorization_url"]
    order.save()

    order.selected_shipping_option = selected_shipping
    order.save()

    return JsonResponse({
        "payment_url": order.payment_url,
        "shipping_options": data["shipping_options"]
    })

def resume_payment(request, reference):

    try:
        order = Order.objects.get(reference=reference)
    except Order.DoesNotExist:
        return redirect("checkout")

    if order.status != "processing":
        return redirect("checkout")

    amount = int(float(order.total_amount or 0) * 100)

    if amount <= 0:
        return JsonResponse({"error": "Invalid payment amount"}, status=400)

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": order.customer.email,
            "amount": amount,
            "reference": order.reference,
            "callback_url": "http://127.0.0.1:8000/payment/verify/"
        },
        headers={
            "Authorization":  "Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    )

    res = response.json()

    print("PAYSTACK DEBUG:", res)

    if not res.get("status"):
        return JsonResponse({
            "error": res.get("message", "Payment failed"),
        }, status=400)

    if not res.get("status"):
        order.status = "cancelled"
        order.save()
        return redirect("checkout")

def payment_success(request):
    return render(request, "success.html")


from logistics.services.router import route_order, get_central_hub

@transaction.atomic
def verify_payment(request):

    reference = request.GET.get("reference")
    order = Order.objects.get(reference=reference)

    # ✅ VERIFY PAYMENT FIRST (unchanged)

    if order.status == "paid":
        return redirect("payment_success")

    order.status = "paid"
    order.save()

    data = json.loads(order.locked_data)

    total_weight = Decimal(data.get("total_weight", "1"))
    shipping_total = Decimal(data.get("shipping", "0"))

    central_hub = get_central_hub()

    # =========================
    # VENDOR → HUB SHIPMENTS
    # =========================
    vendor_to_hub_total = Decimal("0.00")

    for v in data["vendors_data"]:

        vendor = Vendor.objects.get(id=v["vendor_id"])

        # 🔥 Replace with real provider later
        vendor_fee = Decimal("2000")

        vendor_to_hub_total += vendor_fee

        Shipment.objects.create(
            order=order,
            vendor=vendor,
            pickup_address=vendor.address,
            delivery_address=central_hub.address,
            origin_hub=vendor.hub,
            destination_hub=central_hub,
            stage="vendor_to_hub",
            provider="GIGL",
            tracking_id=str(uuid.uuid4()),
            weight=total_weight,
            shipping_fee=vendor_fee,
            total_shipping=vendor_fee
        )

    # =========================
    # HUB → CUSTOMER
    # =========================
    hub_to_customer_fee = shipping_total - vendor_to_hub_total

    Shipment.objects.create(
        order=order,
        vendor=None,
        pickup_address=central_hub.address,
        delivery_address=order.shipping_address,
        origin_hub=central_hub,
        stage="hub_to_customer",
        provider=data.get("selected_provider"),
        tracking_id=str(uuid.uuid4()),
        weight=total_weight,
        shipping_fee=hub_to_customer_fee,
        total_shipping=hub_to_customer_fee
    )

    # =========================
    # COMMISSIONS (FIXED)
    # =========================
    PLATFORM_PERCENT = Decimal("0.05")

    for item in order.items.all():

        product_commission = item.total * PLATFORM_PERCENT

        # 🔥 DISTRIBUTE SHIPPING PROFIT
        shipping_commission = (shipping_total * PLATFORM_PERCENT) / order.items.count()

        Commission.objects.create(
            order=order,
            order_item=item,
            vendor=item.vendor,
            product_commission=product_commission,
            shipping_commission=shipping_commission,
            total_commission=product_commission + shipping_commission
        )

    return redirect("payment_success")
