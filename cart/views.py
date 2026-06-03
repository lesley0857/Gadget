
# Create your views here.
import json
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem
from catalog.models import ProductListing
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_POST
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .utils import *
from cart.models import Cart
from orders.models import *
from logistics.services.aggregator import LogisticsAggregator
from decimal import Decimal
from accounts.models import UserProfile
from urllib.parse import quote

import uuid
import requests
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import JsonResponse

from .models import NegotiationRequest

def add_to_cart(request, listing_id):

    if request.method == "POST":

        listing = get_object_or_404(
            ProductListing,
            id=listing_id
        )

        cart_items_data = []
        total = 0

        # ===================================
        # AUTHENTICATED USER
        # ===================================

        if request.user.is_authenticated:

            cart, _ = Cart.objects.get_or_create(
                user=request.user
            )

            item, created = CartItem.objects.get_or_create(
                cart=cart,
                product_listing=listing
            )

            if not created:
                item.quantity += 1
                item.save()

            items = cart.items.all()

            for i in items:

                price = i.product_listing.calculate_price()
                subtotal = price * i.quantity

                image = ""

                media = i.product_listing.media.filter(
                    is_primary=True
                ).first()

                if media:
                    image = media.file.url

                cart_items_data.append({
                    "id": i.product_listing.id,
                    "name": i.product_listing.product.name,
                    "price": float(price),
                    "quantity": i.quantity,
                    "subtotal": float(subtotal),
                    "image": image
                })

                total += subtotal

        # ===================================
        # ANONYMOUS USER
        # ===================================

        else:

            cart = request.session.get("cart", {})

            # ADD OR INCREMENT
            if str(listing_id) in cart:

                cart[str(listing_id)]["quantity"] += 1

            else:

                cart[str(listing_id)] = {
                    "quantity": 1
                }

            request.session["cart"] = cart
            request.session.modified = True

            # REBUILD RESPONSE
            for id, item in cart.items():

                p = ProductListing.objects.get(id=id)

                quantity = item["quantity"]

                price = p.calculate_price()

                subtotal = price * quantity

                image = ""

                media = p.media.filter(
                    is_primary=True
                ).first()

                if media:
                    image = media.file.url

                cart_items_data.append({
                    "id": p.id,
                    "name": p.product.name,
                    "price": float(price),
                    "quantity": quantity,
                    "subtotal": float(subtotal),
                    "image": image
                })

                total += subtotal

        # ===================================
        # RETURN RESPONSE
        # ===================================
        
        return JsonResponse({
            "success": True,
            "cart_items": cart_items_data,
            "total": float(total),
            "cart_count": len(cart_items_data)
        })

    return JsonResponse({
        "success": False
    }, status=400)

def remove_from_cart(request, listing_id):
    if request.user.is_authenticated:
        cart = Cart.objects.get(user=request.user)
        CartItem.objects.filter(cart=cart, product_listing_id=listing_id).delete()

    else:
        cart = request.session.get('cart', {})

        if str(listing_id) in cart:
            del cart[str(listing_id)]

        request.session['cart'] = cart

    return redirect('cart')

def cart_view(request):
    items = []
    total = 0

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)

        for item in cart.items.all():
            items.append({
                'listing': item.product_listing,
                'quantity': item.quantity,
                'total_price': item.get_total_price(),
                'id': item.product_listing.id
            })

            total += item.get_total_price()

    else:
        session_cart = request.session.get('cart', {})

        for listing_id, data in session_cart.items():
            listing = ProductListing.objects.get(id=listing_id)
            quantity = data['quantity']
            total_price = listing.final_price * quantity

            items.append({
                'listing': listing,
                'quantity': quantity,
                'total_price': total_price,
                'id': listing.id
            })

            total += total_price

    return render(request, 'cart.html', {
        'items': items,
        'total': total
    })

@require_POST
def update_cart(request):
    listing_id = request.POST.get("product_id")
    action = request.POST.get("action")

    if request.user.is_authenticated:
        cart = Cart.objects.get(user=request.user)

        if cart.status == "locked":
            return JsonResponse({
                "success": False,
                "error": "Cart is locked. Complete payment."
            }, status=400)

        try:
            item = CartItem.objects.get(cart=cart, product_listing_id=listing_id)
        except CartItem.DoesNotExist:
            item = None

        if item:
            if action == "increment":
                item.quantity += 1
                item.save()

            elif action == "decrement":
                item.quantity -= 1
                if item.quantity <= 0:
                    item.delete()
                else:
                    item.save()

            elif action == "remove":
                item.delete()

        items = cart.items.all()

    else:
        cart = request.session.get("cart", {})

        if listing_id in cart:
            if action == "increment":
                cart[listing_id]["quantity"] += 1

            elif action == "decrement":
                cart[listing_id]["quantity"] -= 1
                if cart[listing_id]["quantity"] <= 0:
                    del cart[listing_id]

            elif action == "remove":
                del cart[listing_id]

        request.session["cart"] = cart

        items = []
        for id, item in cart.items():
            p = ProductListing.objects.get(id=id)
            items.append({
                "product_listing": p,
                "quantity": item["quantity"]
            })

    # 🔥 ALWAYS REBUILD RESPONSE (NO EARLY RETURN)
    cart_items_data = []
    total = 0

    for i in items:
        if request.user.is_authenticated:
            listing = i.product_listing
            quantity = i.quantity
        else:
            listing = i["product_listing"]
            quantity = i["quantity"]

        price = listing.calculate_price()
        subtotal = price * quantity

        cart_items_data.append({
            "id": listing.id,
            "name": listing.product.name,
            "price": float(price),
            "quantity": quantity,
            "subtotal": float(subtotal),
            "image": listing.media.first().file.url if listing.media.exists() else ""
        })

        total += subtotal
    cart_count = len(cart_items_data)
    return JsonResponse({
        "success": True,
        "cart_items": cart_items_data,
        "total": float(total),
        "cart_count":cart_count,
    })

def cart_summary(request):

    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()

        if not cart:
            return JsonResponse({
                "cart_count": 0,
                "total": 0,
                "cart_items": []
            })

        items = cart.items.all()

        cart_items_data = []
        total = 0
        count = 0

        for item in items:
            listing = item.product_listing
            price = listing.calculate_price()
            subtotal = price * item.quantity

            cart_items_data.append({
                "id": listing.id,
                "name": listing.product.name,
                "price": float(price),
                "quantity": item.quantity,
                "subtotal": float(subtotal),
                "image": listing.media.first().file.url if listing.media.exists() else ""
            })

            total += subtotal

            # ✅ FIXED
            count += item.quantity
        count = len(cart_items_data)

    else:
        cart = request.session.get("cart", {})

        cart_items_data = []
        total = 0
        count = 0

        for id, item in cart.items():
            listing = ProductListing.objects.get(id=id)
            price = listing.calculate_price()
            subtotal = price * item["quantity"]

            cart_items_data.append({
                "id": listing.id,
                "name": listing.product.name,
                "price": float(price),
                "quantity": item["quantity"],
                "subtotal": float(subtotal),
                "image": listing.media.first().file.url if listing.media.exists() else ""
            })

            total += subtotal

            # ✅ FIXED
            count += item["quantity"]
        count = len(cart_items_data)
        
    return JsonResponse({
        "cart_items": cart_items_data,
        "total": float(total),
        "cart_count": count
    })

@login_required
def negotiate_cart(request):

    cart = get_object_or_404(
        Cart,
         user=request.user
    )

    profile = request.user.userprofile

    negotiation = NegotiationRequest.objects.create(

        user=request.user,

        customer_name=request.user.get_full_name(),

        customer_phone=profile.phone
    )

    lines = []

    total = 0

    for item in cart.items.all():

        price = item.product_listing.calculate_price()

        NegotiationItem.objects.create(

            negotiation=negotiation,

            product_listing=item.product_listing,

            quantity=item.quantity,

            original_price=price
        )

        subtotal = price * item.quantity

        total += subtotal

        lines.append(
            f"""
                {item.product_listing.product.name}

                Qty: {item.quantity}

                Price: ₦{price:,.2f}
            """
        )

    message = f"""
        Hello Remarobe,

        I want to negotiate the following products.

        Negotiation Code:
        {negotiation.code}

        {chr(10).join(lines)}

        Current Total:
        ₦{total:,.2f}
        """

    whatsapp = "2348100911189"

    url = (
        f"https://wa.me/{whatsapp}"
        f"?text={quote(message)}"
    )

    return redirect(url)

@login_required
def negotiation_lookup(request):

    negotiation = None

    if request.method == "POST":

        code = request.POST.get("code")
        print(code)

        negotiation = NegotiationRequest.objects.filter(
            code=code
        ).first()
        print(negotiation)
        if negotiation:
            print('True')
            return render(request,"edit_negotiation.html",
                {"negotiation": negotiation}
            )
    return render(
        request,
        "admin_negotiation_lookup.html",
        {
            "negotiation": negotiation
        }
    )

@login_required
def edit_negotiation(request, pk):

    negotiation = get_object_or_404(
        NegotiationRequest,
        pk=pk
    )
    print(f'neg{negotiation}')

    if request.method == "POST":
        print('lllkkgyuguf')
        shipping = request.POST.get(
            "shipping_fee"
        )

        negotiation.shipping_fee = shipping

        negotiation.status = "quoted"

        negotiation.save()

        for item in negotiation.items.all():

            price = request.POST.get(
                f"price_{item.id}"
            )

            item.negotiated_price = price

            item.save()

            send_negotiation_email(request,negotiation)
            

        return redirect(
            'negotiation_detail',
        code=negotiation.code
        )

    return render(
        request,
        "edit_negotiation.html",
        {
            "negotiation": negotiation
        }
    )

@login_required
def negotiation_detail(request, code):

    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )
    print(f'oo{negotiation}')
    total = sum(
        i.get_total()
        for i in negotiation.items.all()
    )

    total += negotiation.shipping_fee

    return render(
        request,
        "negotiation_detail.html",
        {
            "negotiation": negotiation,
            "total": total
        }
    )

@login_required
def user_negotiation_ready_view(request,code):
    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )
    total = sum(
        i.get_total()
        for i in negotiation.items.all()
    )

    total += negotiation.shipping_fee
    return render(request,"users_negotiation_view.html",
        {
            'negotiation':negotiation,
            'total':total
        }
    )

@transaction.atomic
def verify_negotiated_payment(request):

    reference = request.GET.get(
        "reference"
    )

    negotiation = NegotiationRequest.objects.get(
        payment_reference=reference
    )

    if negotiation.status == "paid":

        return redirect(
            "payment_success"
        )

    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={
            "Authorization":
                f"Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    )

    paystack_data = response.json()

    if (
        not paystack_data.get("status")
        or
        paystack_data["data"]["status"]
        != "success"
    ):

        return JsonResponse({
            "error":
            "Payment verification failed"
        })

    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += item.get_total()

    total = subtotal + negotiation.shipping_fee

    order = Order.objects.create(
        customer=negotiation.user,
        total_amount=total,
        email = negotiation.user.email,
        phone = negotiation.customer_phone,
        shipping_amount=
            negotiation.shipping_fee,
        subtotal=subtotal,
        reference=reference,
        status="paid",
        created_at=timezone.now(),
        shipping_address=
            negotiation.shipping_address
    )

    for item in negotiation.items.all():

        vendor = item.product_listing.vendor

        unit_price = item.get_price()

        line_total = (
            unit_price *
            item.quantity
        )

        commission = (
            line_total *
            Decimal("0.05")
        )

        escrow_amount = (
            line_total -
            commission
        )

        OrderItem.objects.create(

            order=order,

            product_listing=
                item.product_listing,

            vendor=vendor,

            quantity=item.quantity,

            price=unit_price,

            total=line_total,

            commission=commission,

            escrow_amount=escrow_amount,

            status="pending"
        )

    negotiation.status = "paid"
    negotiation.order = order
    negotiation.save()

    return redirect(
        "payment_success"
    )

def pay_negotiation(request, code):

    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )

    if negotiation.status == "paid":

        return JsonResponse({
            "error": "This quotation has already been paid."
        }, status=400)

    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += (
            item.negotiated_price *
            item.quantity
        )

    total = subtotal + negotiation.shipping_fee

    payment_reference = f"NEG-{uuid.uuid4().hex[:12]}"

    negotiation.payment_reference = payment_reference
    negotiation.save()

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": negotiation.user.email,
            "amount": int(total * 100),
            "reference": payment_reference,
            "callback_url":
                "http://127.0.0.1:8000/negotiation/payment/verify/"
        },
        headers={
            "Authorization":
                f"Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    )

    data = response.json()

    if not data.get("status"):

        return JsonResponse({
            "error": data.get("message")
        }, status=400)

    return redirect(
        data["data"]["authorization_url"]
    )


@login_required
def checkout_view(request):
    user = request.user

    # =========================
    # CART SAFETY CHECK
    # =========================
    cart = Cart.objects.filter(user=user).first()
    if not cart or cart.items.count() == 0:
        return render(request, "checkout.html", {
            "items": [],
            "vendors_data": [],
            "subtotal": 0,
            "shipping": 0,
            "vat": 0,
            "total": 0,
            "shipping_options": []
        })

    items = cart.items.all()

    profile, created = UserProfile.objects.get_or_create(user=user)

    missing_profile = False

    if not profile.address or not profile.phone:
        missing_profile = True

    # =========================
    # CORE BUILD (DO ALL LOGIC HERE)
    # =========================
    data = build_vendor_checkout(user)

    # =========================
    # CANCEL OLD PROCESSING ORDER SAFELY
    # =========================
    Order.objects.filter(
        customer=user,
        status="processing"
    ).update(status="cancelled")

    # =========================
    # SAFE SHIPPING EXTRACTION
    # =========================
    shipping_options = data.get("shipping_options") or []

    # =========================
    # CONTEXT (NO OVERWRITES)
    # =========================
    context = {
        "items": items,
        "vendors_data": data.get("vendors_data", []),

        "subtotal": data.get("subtotal", 0),
        "shipping": data.get("shipping", 0),
        "vat": data.get("vat", 0),
        "total": data.get("total", 0),
        "vendor_to_hub_total":
            data.get("vendor_to_hub_total", 0),
        "shipping_options": shipping_options,
        "missing_profile":missing_profile,
    }

    return render(request, "checkout.html", context)


def update_checkout(request):
    data = json.loads(request.body)
    shipping_choices = data.get("shipping", {})

    user = request.user
    checkout = build_vendor_checkout(user, shipping_choices)

    return JsonResponse({
        "shipping": checkout["shipping"],
        "total": checkout["total"]
    })
def save_shipping(request):
    data = json.loads(request.body)
    request.session["shipping_option"] = data["option"]

    return JsonResponse({"success": True})