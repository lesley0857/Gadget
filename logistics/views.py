from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from orders.models import Order
from .models import Shipment, LogisticsRate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib import messages

from cart.utils import build_vendor_checkout
from .utils import (
    serialize_decimals,
    send_shipping_negotiation_email,
    build_shipping_whatsapp_url,
    haversine_distance,
    calculate_shipping_fee,
    resolve_vendor_coords,
    resolve_city_coords,
    estimate_cart_shipping_fee,
)
from .nigeria_cities import suggest_cities


# ============================================================
# TRACK ORDER
# ============================================================

@login_required
def track_order(request, order_number):
    order = get_object_or_404(
        Order,
        order_number=order_number,
        customer=request.user
    )

    shipment = Shipment.objects.filter(order=order).first()

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

    current_step = status_steps.get(order.status, 1)
    if shipment:
        current_step = status_steps.get(shipment.status, current_step)

    return render(
        request,
        "track_order.html",
        {
            "order": order,
            "shipment": shipment,
            "current_step": current_step,
        },
    )


# ============================================================
# DELIVERY DASHBOARD
# ============================================================

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
        {"shipments": shipments},
    )


# ============================================================
# UPDATE SHIPMENT STATUS
# ============================================================

@login_required
def update_shipment_status(request, shipment_id):
    shipment = get_object_or_404(Shipment, id=shipment_id)

    if request.method == "POST":
        shipment.status = request.POST.get("status")
        shipment.last_update = timezone.now()

        if shipment.status == "delivered":
            shipment.delivered_at = timezone.now()
            shipment.order.status = "delivered"
            shipment.order.save()
        elif shipment.status == "out_for_delivery":
            shipment.order.status = "out_for_delivery"
            shipment.order.save()
        elif shipment.status in ["picked", "in_transit", "at_hub"]:
            shipment.order.status = "shipped"
            shipment.order.save()

        shipment.save()
        messages.success(request, "Shipment updated successfully.")

    return redirect("delivery_dashboard")


# ============================================================
# LOGISTICS CALCULATOR PAGE (standalone tool)
# ============================================================

def logistics_calculator_page(request):
    from accounts.models import Vendor
    vendors = Vendor.objects.filter(verified=True).order_by("store_name")
    if not vendors.exists():
        vendors = Vendor.objects.all().order_by("store_name")
    rates = LogisticsRate.objects.filter(is_active=True).order_by("min_km")
    return render(
        request,
        "logistics_calculator.html",
        {
            "vendors": vendors,
            "rates": rates,
        },
    )


# ============================================================
# AJAX: CALCULATE LOGISTICS FEE
# ============================================================

@require_POST
def calculate_logistics_fee_api(request):
    """
    AJAX endpoint called from checkout and standalone calculator.

    POST body (JSON or form):
        vendor_id       int  (optional, for standalone calculator)
        customer_lat    float
        customer_lon    float
        city_name       str  (used if lat/lon not provided)
        weight_kg       float (default 1.0)

    Returns JSON fee breakdown.
    """
    import json
    from decimal import Decimal

    # Parse JSON or form data
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body)
        else:
            data = request.POST
    except (ValueError, Exception):
        data = request.POST

    # Resolve customer coordinates
    customer_lat = data.get("customer_lat", "")
    customer_lon = data.get("customer_lon", "")
    city_name = data.get("city_name", "")
    weight_kg = float(data.get("weight_kg", 1.0))
    vendor_id = data.get("vendor_id", "")

    # Try lat/lon first, then city lookup
    try:
        clat = float(customer_lat)
        clon = float(customer_lon)
    except (TypeError, ValueError):
        coords = resolve_city_coords(city_name)
        if not coords:
            return JsonResponse(
                {"error": "Could not resolve customer location. Please use GPS or enter a valid city name."},
                status=400,
            )
        clat, clon = coords

    # Resolve vendor(s)
    from accounts.models import Vendor
    from cart.models import Cart

    if vendor_id:
        # Standalone calculator: single vendor
        try:
            vendor = Vendor.objects.get(pk=int(vendor_id))
            vendors_list = [vendor]
        except (Vendor.DoesNotExist, ValueError):
            return JsonResponse({"error": "Vendor not found."}, status=400)
    elif request.user.is_authenticated:
        # Checkout: all vendors in the user's cart
        try:
            cart = Cart.objects.get(user=request.user)
            vendor_ids = cart.items.values_list(
                "product_listing__vendor", flat=True
            ).distinct()
            vendors_list = list(Vendor.objects.filter(pk__in=vendor_ids))
        except Cart.DoesNotExist:
            vendors_list = []
    else:
        # Checkout: guest session cart
        session_cart = request.session.get("cart", {})
        from catalog.models import ProductListing
        listing_ids = [int(k) for k in session_cart.keys() if str(k).isdigit()]
        vendor_ids = ProductListing.objects.filter(pk__in=listing_ids).values_list("vendor", flat=True).distinct()
        vendors_list = list(Vendor.objects.filter(pk__in=vendor_ids))

    if not vendors_list:
        # Fallback to any active vendor so calculation doesn't hard-fail
        vendors_list = list(Vendor.objects.all()[:1])

    if not vendors_list:
        return JsonResponse({"error": "No vendors found."}, status=400)

    breakdown = estimate_cart_shipping_fee(vendors_list, clat, clon, weight_kg)

    # Convert Decimals to float for JSON
    result = {
        "distance_km": breakdown["distance_km"],
        "base_fee": float(breakdown["base_fee"]),
        "distance_cost": float(breakdown["distance_cost"]),
        "weight_cost": float(breakdown["weight_cost"]),
        "subtotal": float(breakdown["subtotal"]),
        "margin": float(breakdown["margin"]),
        "total": float(breakdown["total"]),
        "rate_label": breakdown["rate_label"],
        "farthest_vendor": breakdown.get("farthest_vendor", ""),
        "vendor_distances": breakdown.get("vendor_distances", []),
        "customer_lat": clat,
        "customer_lon": clon,
    }
    return JsonResponse(result)


# ============================================================
# AJAX: CITY AUTOCOMPLETE
# ============================================================

def city_lookup_api(request):
    """
    GET /logistics/api/city-lookup/?q=lag
    Returns up to 8 matching Nigerian city names with coordinates.
    """
    q = request.GET.get("q", "").strip()
    suggestions = suggest_cities(q, limit=8)
    return JsonResponse({"results": suggestions})
