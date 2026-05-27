
# Create your views here.
import json
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem
from catalog.models import ProductListing
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from .utils import *
from cart.models import Cart
from orders.models import *
from logistics.services.aggregator import LogisticsAggregator
from decimal import Decimal

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
            "cart_count": sum(
                item["quantity"]
                for item in cart_items_data
            )
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

    cart_count = sum([item["quantity"] for item in cart_items_data])
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
            count += 1

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
            count += 1

    return JsonResponse({
        "cart_items": cart_items_data,
        "total": float(total),
        "cart_count": count
    })

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