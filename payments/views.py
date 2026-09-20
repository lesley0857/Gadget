import os
import json
# Create your views here.
import requests
import uuid

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import Http404
from decimal import Decimal, ROUND_HALF_UP
from django.urls import reverse
from orders.models import *
from django.http import JsonResponse
from django.conf import settings
from cart.models import *

from logistics.models import Shipment
from logistics.utils import serialize_decimals
from cart.utils import *
from collections import defaultdict
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
from wallets.models import VendorWallet, WalletTransaction, Commission
from accounts.models import Vendor, User
from pricing.services import calculate_checkout_pricing

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

@require_POST
@transaction.atomic
def initiate_payment(request):

    user = request.user
    # Guest purchases receive a non-login, unusable account so existing
    # order, escrow and vendor relations remain intact.
    if not user.is_authenticated:
        guest_id = uuid.uuid4().hex
        user = User.objects.create_user(username=f"guest-{guest_id}", email=f"guest-{guest_id}@checkout.remarobe.invalid")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        guest_cart = Cart.objects.create(user=user)
        for listing_id, row in request.session.get("cart", {}).items():
            listing = ProductListing.objects.filter(pk=listing_id).first()
            if listing:
                CartItem.objects.create(cart=guest_cart, product_listing=listing, quantity=max(1, int(row.get("quantity", 1))))

    required_fields = [

        "first_name",

        "last_name",

        "email",

        "phone",

        "address",

        "city",

        "state",
        "shipping_address",
        "shipping_city",
        "shipping_state",
        "shipping_phone",
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
    # REBUILD CHECKOUT FRESH & CALCULATE SHIPPING
    # =====================================

    checkout = build_vendor_checkout(user)

    from logistics.utils import estimate_cart_shipping_fee, resolve_city_coords
    from accounts.models import Vendor

    cart = Cart.objects.filter(user=user).first()
    vendors_in_cart = []
    total_weight = 0.0
    if cart:
        vendor_ids = cart.items.values_list("product_listing__vendor", flat=True).distinct()
        vendors_in_cart = list(Vendor.objects.filter(pk__in=vendor_ids))
        for ci in cart.items.select_related("product_listing"):
            total_weight += float(ci.product_listing.weight or 0) * ci.quantity

    clat = None
    clon = None
    post_lat = request.POST.get("customer_lat")
    post_lon = request.POST.get("customer_lon")
    post_city = request.POST.get("shipping_city") or request.POST.get("city") or request.POST.get("shipping_state") or request.POST.get("state")

    if post_lat and post_lon:
        try:
            clat = float(post_lat)
            clon = float(post_lon)
        except (ValueError, TypeError):
            pass

    if (clat is None or clon is None) and post_city:
        coords = resolve_city_coords(post_city)
        if coords:
            clat, clon = coords

    base_shipping = Decimal(str(checkout.get("shipping", "0.00")))
    logistics_fee = Decimal("0.00")
    if vendors_in_cart and clat is not None and clon is not None:
        fee_data = estimate_cart_shipping_fee(vendors_in_cart, clat, clon, total_weight)
        logistics_fee = Decimal(str(fee_data.get("total", "0.00")))
    elif request.POST.get("shipping_fee"):
        try:
            passed_fee = Decimal(str(request.POST.get("shipping_fee", "0")))
            if passed_fee > base_shipping:
                logistics_fee = passed_fee - base_shipping
            elif passed_fee > 0 and base_shipping == 0:
                logistics_fee = passed_fee
        except (ValueError, Exception):
            pass

    local_state = os.getenv("REMAROBE_LOCAL_DELIVERY_STATE", "Lagos").strip().lower()
    destination_state = request.POST.get("shipping_state", "").strip().lower()
    if destination_state and destination_state != local_state and logistics_fee == 0 and base_shipping == 0:
        base_shipping += Decimal(os.getenv("REMAROBE_OUT_OF_STATE_DELIVERY_FEE", "0"))

    # Shipping fee combines product fixed fee + logistics distance fee
    shipping_fee = base_shipping + logistics_fee

    # If shipping_fee was confirmed on checkout page by customer, honor it
    post_shipping = request.POST.get("shipping_fee")
    if post_shipping:
        try:
            passed_shipping = Decimal(str(post_shipping)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if passed_shipping >= Decimal("0.00"):
                shipping_fee = passed_shipping
        except (ValueError, TypeError):
            pass

    requires_shipping = checkout.get(
        "requires_shipping",
        False
    ) or (shipping_fee > 0)

    requires_shipping_negotiation = (
        checkout.get(
            "requires_negotiation",
            False
        )
    )

    subtotal = Decimal(
        str(checkout["subtotal"])
    )

    pricing = calculate_checkout_pricing(
        subtotal=subtotal,
        shipping=shipping_fee
    )

    # CRITICAL: Always ensure payment amount sent to Paystack matches the checkout total confirmed by the user at click
    post_checkout_total = request.POST.get("checkout_total")
    if post_checkout_total:
        try:
            confirmed_total = Decimal(str(post_checkout_total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if confirmed_total > Decimal("0.00"):
                pricing.total = confirmed_total
                pricing.net_total = confirmed_total
                pricing.paystack_amount_kobo = int(confirmed_total * 100)
        except (ValueError, TypeError):
            pass

    reference = str(
        uuid.uuid4()
    )

    # =====================================
    # LOCKED SNAPSHOT
    # =====================================

    locked_snapshot = serialize_decimals({
        **checkout,
        "subtotal": pricing.subtotal,
        "shipping": pricing.shipping,
        "net_total": pricing.net_total,
        "amount_before_gateway_fee": pricing.net_total,
        "gateway_fee": pricing.gateway_fee,
        "total": pricing.total,
        "paystack_amount": pricing.paystack_amount_kobo,
    })
    
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
        subtotal=pricing.subtotal,
        shipping_amount=pricing.shipping,
        shipping_fee=pricing.shipping,
        amount_before_gateway_fee=pricing.net_total,
        gateway_fee=pricing.gateway_fee,
        total_amount=pricing.total,
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
    PAYSTACK_SECRET_KEY = settings.PAYSTACK_SECRET_KEY
    if not PAYSTACK_SECRET_KEY:
        order.status = "cancelled"
        order.save(update_fields=["status"])
        return JsonResponse({"error": "Payment service is not configured."}, status=503)

    try:
        response = requests.post(

        "https://api.paystack.co/"
        "transaction/initialize",

        json={

            "email":
                request.POST.get("email"),

            "amount":
                pricing.paystack_amount_kobo,

            "reference":
                reference,

            "callback_url":
                callback,

            "metadata": {"order_id": order.id},
        },

        headers={

            "Authorization":f"Bearer {PAYSTACK_SECRET_KEY}"
        }, timeout=15)
        response.raise_for_status()
        paystack = response.json()
    except (requests.RequestException, ValueError):
        order.status = "cancelled"
        order.save(update_fields=["status"])
        return JsonResponse({"error": "Payment service is temporarily unavailable."}, status=503)

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


@login_required
@require_POST
def resume_payment(request, reference):

    try:
        order = Order.objects.get(reference=reference, customer=request.user)
    except Order.DoesNotExist:
        return redirect("checkout")

    if order.status != "processing":
        return redirect("checkout")

    amount = int(Decimal(str(order.total_amount or 0)) * 100)

    if amount <= 0:
        return JsonResponse({"error": "Invalid payment amount"}, status=400)
    PAYSTACK_SECRET_KEY = settings.PAYSTACK_SECRET_KEY
    callback = (
        request.build_absolute_uri(
            reverse(
                "verify_payment"
            )
        )
    )
    
    if not PAYSTACK_SECRET_KEY:
        return JsonResponse({"error": "Payment service is not configured."}, status=503)
    try:
        response = requests.post(
            "https://api.paystack.co/transaction/initialize",
            json={"email": order.customer.email, "amount": amount, "reference": order.reference,
                  "callback_url": callback, "metadata": {"order_id": order.id}},
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}, timeout=15,
        )
        response.raise_for_status()
        res = response.json()
    except (requests.RequestException, ValueError):
        return JsonResponse({"error": "Payment service is temporarily unavailable."}, status=503)

    if not res.get("status"):
        return JsonResponse({
            "error": res.get("message", "Payment failed"),
        }, status=400)

    order.payment_url = res["data"]["authorization_url"]
    order.save(update_fields=["payment_url"])
    return redirect(order.payment_url)


def payment_success(request):
    return render(request, "success.html")

@transaction.atomic
@require_GET
def verify_payment(request):

    reference = request.GET.get(
        "reference"
    )

    if not reference:
        raise Http404("Payment reference not found")
    try:
        order = Order.objects.select_for_update().get(reference=reference)
    except Order.DoesNotExist:
        raise Http404("Payment reference not found")

    if order.status == "paid":

        return redirect(
            "payment_success"
        )
    PAYSTACK_SECRET_KEY = settings.PAYSTACK_SECRET_KEY
    if not PAYSTACK_SECRET_KEY:
        return JsonResponse({"error": "Payment service is not configured."}, status=503)
    try:
        response = requests.get(

        f"https://api.paystack.co/"
        f"transaction/verify/"
        f"{reference}",

        headers={

            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"
        

        }, timeout=15)
        response.raise_for_status()
        paystack = response.json()
    except (requests.RequestException, ValueError):
        return JsonResponse({"error": "Payment verification is temporarily unavailable."}, status=503)

    if (

        not paystack.get("status")

        or paystack.get("data", {}).get("status") != "success"
        or paystack.get("data", {}).get("reference") != reference
        or Decimal(str(paystack.get("data", {}).get("amount", 0))) != order.total_amount * 100
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
    order.amount_paid = order.total_amount
    order.save()

    # Credit vendor escrow and update order items
    for item in order.items.select_related("vendor", "product_listing"):
        item.status = "paid"
        item.save(update_fields=["status"])

        if item.vendor:
            wallet, _ = VendorWallet.objects.get_or_create(vendor=item.vendor)
            wallet.escrow_balance += item.escrow_amount
            wallet.save(update_fields=["escrow_balance"])

            WalletTransaction.objects.create(
                wallet=wallet,
                amount=item.escrow_amount,
                type="credit",
                reference=order.reference,
                description=f"Escrow hold for Order #{order.order_number or order.id} - {item.product_listing.name}"
            )

            Commission.objects.get_or_create(
                order=order,
                order_item=item,
                vendor=item.vendor,
                defaults={
                    "product_commission": item.commission,
                    "shipping_commission": Decimal("0.00"),
                    "total_commission": item.commission,
                }
            )

    data = order.locked_data

    if not order.requires_shipping_negotiation:
        if data and data.get("requires_shipping"):
            Shipment.objects.create(
                order=order,
                tracking_id=str(uuid.uuid4()),
                provider="Remarobe Logistics",
                delivery_address=order.shipping_address or "",
                status="created",
            )

    cart = Cart.objects.filter(user=order.customer).first()
    if cart:
        cart.items.all().delete()
        cart.status = "active"
        cart.save()
    request.session["cart"] = {}
    request.session.modified = True

    return redirect("payment_success")


