# logistics/utils.py
import math
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .nigeria_cities import (
    lookup_city,
    lookup_state_centroid,
    suggest_cities,
)

# ---------------------------------------------------------------------------
# DEFAULT RATE — used when no LogisticsRate rows exist in the database
# ---------------------------------------------------------------------------
DEFAULT_BASE_FEE = Decimal("500.00")
DEFAULT_RATE_PER_KM = Decimal("50.00")
DEFAULT_WEIGHT_RATE_PER_KG = Decimal("30.00")
DEFAULT_FREE_WEIGHT_KG = Decimal("1.00")


# ---------------------------------------------------------------------------
# HAVERSINE DISTANCE
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in kilometres between two points
    on the Earth's surface using the Haversine formula.
    """
    R = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# RATE RESOLUTION
# ---------------------------------------------------------------------------

def get_active_rate(distance_km: float):
    """
    Return the best matching LogisticsRate database row for a given distance,
    or None if no active rows exist. Import is deferred to avoid circular import.
    """
    from .models import LogisticsRate

    rates = LogisticsRate.objects.filter(is_active=True).order_by("min_km")
    best = None
    for rate in rates:
        if rate.min_km <= distance_km:
            if rate.max_km is None or distance_km < rate.max_km:
                best = rate
    return best


# ---------------------------------------------------------------------------
# FEE CALCULATION
# ---------------------------------------------------------------------------

def calculate_shipping_fee(distance_km: float, weight_kg: float = 1.0) -> dict:
    """
    Compute the end-to-end delivery fee for a given distance and weight.

    Returns a dict:
        distance_km     float
        base_fee        Decimal
        distance_cost   Decimal
        weight_cost     Decimal
        subtotal        Decimal
        margin          Decimal
        total           Decimal
        rate_label      str
    """
    distance_km = float(distance_km)
    weight_kg = float(weight_kg)

    rate = get_active_rate(distance_km)

    if rate:
        base_fee = Decimal(str(rate.base_fee))
        rate_per_km = Decimal(str(rate.rate_per_km))
        weight_rate = Decimal(str(rate.weight_rate_per_kg))
        free_weight = Decimal(str(rate.free_weight_kg))
        rate_label = str(rate.label)
    else:
        base_fee = DEFAULT_BASE_FEE
        rate_per_km = DEFAULT_RATE_PER_KM
        weight_rate = DEFAULT_WEIGHT_RATE_PER_KG
        free_weight = DEFAULT_FREE_WEIGHT_KG
        rate_label = "Standard Rate"

    distance_cost = (Decimal(str(distance_km)) * rate_per_km).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    extra_weight = max(Decimal("0"), Decimal(str(weight_kg)) - free_weight)
    weight_cost = (extra_weight * weight_rate).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    subtotal = base_fee + distance_cost + weight_cost

    margin_pct = Decimal(
        str(getattr(settings, "SHIPPING_MARGIN_PERCENT", 0.15))
    )
    margin = (subtotal * margin_pct).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    total = subtotal + margin

    return {
        "distance_km": round(distance_km, 2),
        "base_fee": base_fee,
        "distance_cost": distance_cost,
        "weight_cost": weight_cost,
        "subtotal": subtotal,
        "margin": margin,
        "total": total,
        "rate_label": rate_label,
    }


# ---------------------------------------------------------------------------
# COORDINATE RESOLVERS
# ---------------------------------------------------------------------------

def resolve_vendor_coords(vendor):
    """
    Return (lat, lon) for a vendor.
    Priority:
      1. vendor.latitude / vendor.longitude (already stored)
      2. State centroid for vendor.state
      3. Lagos centroid as final fallback
    Returns (float, float).
    """
    try:
        lat = float(vendor.latitude)
        lon = float(vendor.longitude)
        if lat != 0.0 and lon != 0.0:
            return lat, lon
    except (TypeError, ValueError):
        pass

    # Fallback: state centroid
    state_name = str(vendor.state) if vendor.state else None
    centroid = lookup_state_centroid(state_name) if state_name else None
    if centroid:
        return centroid

    # Final fallback: Lagos
    return (6.4541, 3.3947)


def resolve_city_coords(city_name: str):
    """
    Return (lat, lon) for a Nigerian city name, or None if not found.
    """
    return lookup_city(city_name)


def geocode_address(address: str, city: str, state: str):
    """
    Attempt to resolve lat/lon from address components.
    Tries city first, then state centroid.
    Returns (lat, lon) or (None, None).
    """
    coords = lookup_city(city) if city else None
    if coords:
        return coords

    coords = lookup_city(address) if address else None
    if coords:
        return coords

    coords = lookup_state_centroid(state) if state else None
    if coords:
        return coords

    return None, None


def estimate_cart_shipping_fee(vendors_in_cart, customer_lat: float, customer_lon: float, total_weight_kg: float) -> dict:
    """
    Given a list of Vendor objects and the customer's coordinates,
    compute the worst-case (farthest vendor) delivery fee.

    Returns the fee breakdown dict from calculate_shipping_fee plus:
        vendor_distances: list of {vendor_name, distance_km}
        farthest_vendor: str
    """
    if not vendors_in_cart:
        return {
            "distance_km": 0,
            "base_fee": Decimal("0"),
            "distance_cost": Decimal("0"),
            "weight_cost": Decimal("0"),
            "subtotal": Decimal("0"),
            "margin": Decimal("0"),
            "total": Decimal("0"),
            "rate_label": "N/A",
            "vendor_distances": [],
            "farthest_vendor": "",
        }

    vendor_distances = []
    max_distance = 0.0
    farthest_name = ""

    for vendor in vendors_in_cart:
        vlat, vlon = resolve_vendor_coords(vendor)
        dist = haversine_distance(vlat, vlon, customer_lat, customer_lon)
        # For intra-city (same city/area), enforce a realistic baseline delivery radius (5km min)
        if dist < 2.0:
            dist = 5.0
        vendor_distances.append({
            "vendor_name": vendor.store_name,
            "distance_km": round(dist, 2),
        })
        if dist > max_distance:
            max_distance = dist
            farthest_name = vendor.store_name

    breakdown = calculate_shipping_fee(max_distance, total_weight_kg)
    breakdown["vendor_distances"] = vendor_distances
    breakdown["farthest_vendor"] = farthest_name
    return breakdown


# ---------------------------------------------------------------------------
# EXISTING UTILS (preserved)
# ---------------------------------------------------------------------------

def build_shipping_whatsapp_url(negotiation):
    customer = negotiation.customer
    data = negotiation.locked_data
    items = data["items"]
    lines = []
    for item in items:
        lines.append(
            f"{item['name']} "
            f"(Qty: {item['quantity']})"
        )

    message = f"""
Hello Remarobe,

A customer has requested delivery negotiation.

Reference:
{negotiation.code}

Customer:
{customer.get_full_name()}

Email:
{customer.email}

Items:

{chr(10).join(lines)}

Weight:
{data['total_weight']} kg

Subtotal:
\u20a6{data['subtotal']}

Please review this request.

"""
    whatsapp_number = "2348100911189"
    return (
        f"https://wa.me/{whatsapp_number}"
        f"?text={quote(message)}"
    )


def send_shipping_negotiation_email(request, negotiation):
    subtotal = Decimal("0.00")
    customer = negotiation.customer

    for item in negotiation.items.all():
        subtotal += (
            item.original_price *
            item.quantity
        )

    admin_email = settings.ADMIN_EMAIL
    admin_url = request.build_absolute_uri(
        f"/admin/cart/negotiationrequest/{negotiation.id}/change/"
    )
    detail_url = (
        request.build_absolute_uri(
            reverse("admin:index")
        )
    )

    context = {
        "negotiation": negotiation,
        "subtotal": subtotal,
        "admin_url": admin_url,
        "detail_url": detail_url,
    }

    admin_html = render_to_string(
        "emails/shipping_negotiation_admin.html",
        context,
    )

    admin_email_message = EmailMultiAlternatives(
        subject=(
            f"New Shipping Negotiation "
            f"({negotiation.code})"
        ),
        body="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[admin_email],
    )
    admin_email_message.attach_alternative(admin_html, "text/html")
    admin_email_message.send()

    customer_html = render_to_string(
        "emails/shipping_negotiation_customer.html",
        context,
    )

    customer_email = EmailMultiAlternatives(
        subject=(
            "We Received Your "
            "Delivery Request"
        ),
        body="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[customer.email],
    )
    customer_email.attach_alternative(customer_html, "text/html")
    customer_email.send()


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
