from decimal import Decimal
from cart.models import *
from logistics.pricing import calculate_shipping_options
from collections import defaultdict
from logistics.services.aggregator import LogisticsAggregator
from cart.models import *

from collections import defaultdict
from logistics.services.aggregator import LogisticsAggregator

from django.conf import settings

import math


def calculate_checkout(user, selected_option_id=None):

    items = CartItem.objects.filter(cart__user=user)

    subtotal = Decimal("0.00")

    for item in items:
        subtotal += item.product_listing.calculate_price() * item.quantity

    vat = subtotal * Decimal("0.075")

    weight = 2

    shipping_options = calculate_shipping_options(weight)

    if not shipping_options:
        return {
            "subtotal": subtotal,
            "shipping": Decimal("0.00"),
            "vat": vat,
            "total": subtotal + vat,
            "shipping_options": []
        }

    # ✅ USE USER SELECTION
    selected_option = shipping_options[0]

    if selected_option_id:
        for opt in shipping_options:
            if str(opt["id"]) == str(selected_option_id):
                selected_option = opt
                break

    shipping_fee = Decimal(selected_option["fee"])

    total = subtotal + shipping_fee + vat

    return {
        "subtotal": subtotal,
        "shipping": shipping_fee,
        "vat": vat,
        "total": total,
        "shipping_options": shipping_options,
        "selected_option_id": selected_option["id"]
    }

def build_vendor_checkout(user, shipping_choices=None):

    cart = Cart.objects.get(user=user)
    profile = user.userprofile
    aggregator = LogisticsAggregator()

    vendor_map = defaultdict(list)

    for item in cart.items.select_related("product_listing__vendor"):
        vendor_map[item.product_listing.vendor].append(item)

    vendors_data = []
    subtotal = Decimal("0.00")
    total_weight = Decimal("0.00")

    # =========================
    # BUILD VENDOR DATA + ITEMS
    # =========================
    for vendor, items in vendor_map.items():

        vendor_subtotal = Decimal("0.00")
        vendor_weight = Decimal("0.00")
        item_list = []

        for item in items:
            price = Decimal(str(item.product_listing.calculate_price()))
            qty = item.quantity
            weight = Decimal(str(item.product_listing.weight or 1))

            line_total = price * qty

            vendor_subtotal += line_total
            vendor_weight += weight * qty
            total_weight += weight * qty

            item_list.append({
                "product_id": item.product_listing.id,
                "product_name": item.product_listing.product.name,
                "unit_price": str(price),
                "quantity": qty,
                "weight": str(weight),
                "line_total": str(line_total),
            })

        subtotal += vendor_subtotal

        vendors_data.append({
            "vendor_id": vendor.id,
            "vendor_name": vendor.store_name,
            "items": item_list,   # ✅ FIX
            "vendor_subtotal": str(vendor_subtotal),
            "vendor_weight": str(vendor_weight),
        })

    # =========================
    # SHIPPING (HUB → CUSTOMER)
    # =========================
    pickup = {"address": "Lagos Hub"}
    delivery = {"address": profile.address}

    shipping_options = aggregator.get_all_rates(
        pickup,
        delivery,
        float(total_weight)
    ) or []

    selected_option = shipping_options[0] if shipping_options else {
        "id": "default",
        "provider": "Manual",
        "fee": 0
    }

    if shipping_choices:
        for opt in shipping_options:
            if str(opt["id"]) == str(shipping_choices):
                selected_option = opt
                break

    hub_fee = Decimal(str(selected_option.get("fee", 0)))

    # =========================
    # VENDOR → HUB (TEMP FIX)
    # =========================
    vendor_to_hub_total = Decimal("0.00")

    for vendor, items in vendor_map.items():
        vendor_fee = Decimal("2000")  # Replace later with API
        vendor_to_hub_total += vendor_fee

    total_shipping = hub_fee + vendor_to_hub_total

    vat = subtotal * Decimal("0.075")
    total = subtotal + vat + total_shipping

    return {
        "vendors_data": vendors_data,
        "subtotal": str(subtotal),
        "shipping": str(total_shipping),
        "vat": str(vat),
        "total": str(total),

        "shipping_options": shipping_options,
        "selected_shipping_option": selected_option["id"],
        "selected_provider": selected_option["provider"],

        "total_weight": str(total_weight),
        "vendor_to_hub_total": str(vendor_to_hub_total),
        "hub_to_customer_fee": str(hub_fee),
    }