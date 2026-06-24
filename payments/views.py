import os
import json
# Create your views here.
import requests
import uuid

from django.shortcuts import render, redirect
from decimal import Decimal
from django.urls import reverse
from orders.models import *
from django.http import JsonResponse
from cart.models import *

from logistics.models import Shipment
from logistics.utils import serialize_decimals
from cart.utils import *
from collections import defaultdict
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from wallets.models import VendorWallet, WalletTransaction, Commission
from accounts.models import Vendor

from decimal import Decimal


def serialize_decimals(obj):

    if isinstance(obj, Decimal):

        return str(obj)

    elif isinstance(obj, dict):

        return {
            key: serialize_decimals(value)
            for key, value in obj.items()
        }

    elif isinstance(obj, list):

        return [
            serialize_decimals(item)
            for item in obj
        ]

    return obj
# "Authorization":"Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"

@transaction.atomic
def initiate_payment(request):

    user = request.user
 
    required_fields = [

        "first_name",

        "last_name",

        "email",

        "phone",

        "address",

        "city",

        "state",
    ]

    for field in required_fields:

        if not request.POST.get(field):

            return JsonResponse(
                {
                    "error":
                    f"{field} is required"
                },
                status=400
            )

    # =====================================
    # CANCEL OLD PROCESSING ORDERS
    # =====================================

    Order.objects.filter(

        customer=user,

        status="processing",

        created_at__lt=(
            timezone.now()
            - timedelta(hours=1)
        )

    ).update(
        status="cancelled"
    )

    # =====================================
    # REBUILD CHECKOUT FRESH
    # =====================================

    checkout = build_vendor_checkout(
        user
    )

    shipping_fee = Decimal(
        str(checkout["shipping"])
    )

    requires_shipping = checkout.get(
        "requires_shipping",
        False
    )

    requires_shipping_negotiation = (
        checkout.get(
            "requires_negotiation",
            False
        )
    )

    subtotal = Decimal(
        str(checkout["subtotal"])
    )


    # =====================================
    # FINAL TOTAL
    # =====================================

    total = (
        subtotal
        +
        shipping_fee
    )

    reference = str(
        uuid.uuid4()
    )

    # =====================================
    # LOCKED SNAPSHOT
    # =====================================

    locked_snapshot = serialize_decimals({

    **checkout,

    "subtotal": subtotal,

    "shipping": shipping_fee,
    "total": total,
    })
    
    print(f'locked_snapshot{locked_snapshot}')
    request.session[
        "checkout_snapshot"
    ] = locked_snapshot

    request.session.modified = True

    # =====================================
    # CREATE ORDER
    # =====================================

    order = Order.objects.create(

        customer=user,

        reference=reference,
        negotiation=None,
        total_amount=total,

        subtotal=subtotal,

        shipping_amount=shipping_fee,

        shipping_fee=shipping_fee,

        status="processing",

        first_name=request.POST.get(
            "first_name"
        ),

        last_name=request.POST.get(
            "last_name"
        ),

        email=request.POST.get(
            "email"
        ),

        phone=request.POST.get(
            "phone"
        ),

        billing_address=request.POST.get(
            "address"
        ),

        shipping_address=(

            request.POST.get(
                "shipping_address"
            )

            or

            request.POST.get(
                "address"
            )
        ),

        locked_data=locked_snapshot,

        requires_shipping_negotiation=(
            requires_shipping_negotiation
        ),
    )

    # =====================================
    # ORDER ITEMS
    # =====================================

    cart = Cart.objects.get(
        user=user
    )

    for cart_item in cart.items.select_related(

        "product_listing",

        "product_listing__vendor"
    ):

        listing = (
            cart_item.product_listing
        )

        unit_price = Decimal(

            str(
                listing.final_price()
            )
        )

        line_total = (

            unit_price
            *
            cart_item.quantity
        )

        commission = (

            line_total
            *
            Decimal("0.05")
        )

        escrow = (

            line_total
            -
            commission
        )

        OrderItem.objects.create(

            order=order,

            vendor=listing.vendor,

            product_listing=listing,

            quantity=(
                cart_item.quantity
            ),

            price=unit_price,

            total=line_total,

            commission=commission,

            escrow_amount=escrow,

            status="pending",
        )

    print(checkout)
    print(requires_shipping)
    # =====================================
    # PAYSTACK
    # =====================================

    callback = (
        request.build_absolute_uri(
            reverse(
                "verify_payment"
            )
        )
    )
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    response = requests.post(

        "https://api.paystack.co/"
        "transaction/initialize",

        json={

            "email":
                user.email,

            "amount":
                int(total * 100),

            "reference":
                reference,

            "callback_url":
                callback,
        },

        headers={

            "Authorization":f"Bearer {PAYSTACK_SECRET_KEY}"
        }
    )

    paystack = response.json()

    if not paystack.get(
        "status"
    ):

        order.status = "cancelled"

        order.save()

        return JsonResponse(
            {
                "error":
                paystack.get(
                    "message",
                    "Unable to initialize payment."
                )
            },
            status=400
        )

    order.payment_url = (

        paystack["data"][
            "authorization_url"
        ]
    )

    order.save()

    return JsonResponse({

        "success": True,

        "payment_url":
            order.payment_url
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
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    callback = (
        request.build_absolute_uri(
            reverse(
                "verify_payment"
            )
        )
    )
    
    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": order.customer.email,
            "amount": amount,
            "reference": order.reference,
            "callback_url": callback
        },
        headers={
            "Authorization":  f"Bearer {PAYSTACK_SECRET_KEY}"
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

    reference = request.GET.get(
        "reference"
    )

    order = Order.objects.get(
        reference=reference
    )

    if order.status == "paid":

        return redirect(
            "payment_success"
        )
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    response = requests.get(

        f"https://api.paystack.co/"
        f"transaction/verify/"
        f"{reference}",

        headers={

            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
        

        }
    )

    paystack = response.json()

    if (

        not paystack.get("status")

        or paystack["data"][
            "status"
        ]
        != "success"
    ):

        return JsonResponse(

            {
                "error":
                "Payment verification "
                "failed"
            },

            status=400,
        )

    order.status = "paid"

    order.paid_at = timezone.now()

    order.save()

    data = order.locked_data

    if not order.requires_shipping_negotiation:

        
        if data.get(
            "requires_shipping"
        ):

            Shipment.objects.create(

                order=order,

                tracking_id=str(
                    uuid.uuid4()
                ),
                provider="Remarobe Logistics",
            
                delivery_address=order.shipping_address,
                status="created",
            )

    cart = Cart.objects.get(
        user=order.customer
    )

    cart.items.all().delete()

    cart.status = "active"

    cart.save()

    return redirect(
        "payment_success"
    )


