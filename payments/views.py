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
from logistics.services.router import route_order, get_central_hub
from accounts.models import Vendor


def initiate_payment(request):

    user = request.user
    selected_shipping = request.POST.get("shipping_global")
    shipping_choice = request.POST.get("shipping_global")
    data = build_vendor_checkout(user, shipping_choices=shipping_choice)
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

    total = Decimal(str(data["subtotal"])) + Decimal(str(data["vat"])) + Decimal(str(data["shipping"]))
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
            "callback_url": "https://remarobe.com/payment/verify/"
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
    order.selected_provider = data.get("selected_provider")
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


@transaction.atomic
def verify_payment(request):

    reference = request.GET.get("reference")

    order = Order.objects.get(reference=reference)

    # ======================================
    # PREVENT DOUBLE CREDIT
    # ======================================

    if order.status == "paid":
        return redirect("payment_success")

    # ======================================
    # VERIFY PAYSTACK
    # ======================================

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={
            "Authorization":
                "Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    )

    paystack_data = response.json()

    if (
        not paystack_data.get("status")
        or paystack_data["data"]["status"] != "success"
    ):
        return JsonResponse({
            "error": "Payment verification failed"
        }, status=400)

    # ======================================
    # MARK ORDER PAID
    # ======================================

    order.status = "paid"
    order.paid_at = timezone.now()
    order.save()

    data = json.loads(order.locked_data)

        # ======================================
    # CREATE ORDER ITEMS
    # ======================================

    cart = Cart.objects.get(user=order.customer)

    for cart_item in cart.items.select_related(
        "product_listing",
        "product_listing__vendor",
        "product_listing__product"
    ):

        listing = cart_item.product_listing

        vendor = listing.vendor

        quantity = cart_item.quantity

        unit_price = Decimal(
            str(listing.calculate_price())
        )

        line_total = unit_price * quantity

        # Example commission (5%)
        commission = line_total * Decimal("0.05")

        escrow_amount = line_total - commission

        OrderItem.objects.create(
            order=order,

            product_listing=listing,

            vendor=vendor,

            quantity=quantity,

            price=unit_price,

            total=line_total,

            commission=commission,

            escrow_amount=escrow_amount,

            status="pending",
        )

    total_weight = Decimal(
        data.get("total_weight", "1")
    )

    central_hub = get_central_hub()

    # ======================================
    # VENDOR → HUB SHIPMENTS
    # ======================================

    for v in data["vendors_data"]:

        vendor = Vendor.objects.get(
            id=v["vendor_id"]
        )

        skip_vendor_to_hub = v.get(
            "skip_vendor_to_hub",
            False
        )

        if skip_vendor_to_hub:
            continue

        fee = Decimal(
            v.get("vendor_to_hub_fee", "0")
        )

        Shipment.objects.create(
            order=order,

            vendor=vendor,

            provider="GIGL",

            pickup_address=vendor.address,

            delivery_address=central_hub.address,

            origin_hub=vendor.hub,

            destination_hub=central_hub,

            stage="vendor_to_hub",

            weight=Decimal(
                v.get("vendor_weight", "1")
            ),

            shipping_fee=fee,

            total_shipping=fee,

            tracking_id=str(uuid.uuid4()),

            status="processing"
        )

    # ======================================
    # HUB → CUSTOMER SHIPMENT
    # ======================================

    hub_fee = Decimal(
        data.get("hub_to_customer_fee", "0")
    )

    Shipment.objects.create(
        order=order,

        vendor=None,

        provider=data.get("selected_provider"),

        pickup_address=central_hub.address,

        delivery_address=order.shipping_address,

        origin_hub=central_hub,

        destination_hub=None,

        stage="hub_to_customer",

        weight=total_weight,

        shipping_fee=hub_fee,

        total_shipping=hub_fee,

        tracking_id=str(uuid.uuid4()),

        status="processing"
    )

    # ======================================
    # CLEAR CART
    # ======================================

    cart = Cart.objects.get(user=order.customer)

    cart.items.all().delete()

    cart.status = "active"

    cart.save()

    return redirect("payment_success")