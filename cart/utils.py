import math
import smtplib
import hashlib
from decimal import Decimal
from cart.models import *
from collections import defaultdict
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse

def build_vendor_checkout(user=None, session_cart=None):
    """Calculate totals from either an authenticated cart or guest session cart."""
    if user is not None and getattr(user, "is_authenticated", False):
        cart_items = list(Cart.objects.get(user=user).items.select_related("product_listing"))
    else:
        cart_items = []
        for listing_id, row in (session_cart or {}).items():
            product = ProductListing.objects.filter(pk=listing_id).first()
            if product:
                cart_items.append(type("GuestCartItem", (), {"product_listing": product, "quantity": max(1, int(row.get("quantity", 1)))})())

    subtotal = Decimal("0.00")
    total_weight = Decimal("0.00")

    requires_negotiation = False
    requires_shipping = False

    shipping_fee = Decimal("0.00")
    charged_product_ids = set()

    items_data = []

    for item in cart_items:

        product = item.product_listing

        qty = item.quantity

        price = Decimal(
            str(product.final_price())
        )

        line_total = price * qty

        subtotal += line_total

        weight = Decimal(
            str(product.weight or 0)
        )

        total_weight += (
            weight * qty
        )

        # SHIPPING CHECK
        if (
            product.fixed_shipping_fee
            and
            product.fixed_shipping_fee > 0
        ):
            requires_shipping = True

        # NEGOTIATION CHECK
        if product.requires_negotiation or product.shipping_type == "negotiation":
            requires_negotiation = True

        items_data.append({

            "product_id": product.id,

            "name": product.name,

            "quantity": qty,

            "price": str(price),

            "weight": str(weight),

            "shipping_fee": str(product.fixed_shipping_fee or 0),

            "subtotal": str(line_total),
        })

    # HEAVY LOAD RULE
    if total_weight >= Decimal("15"):
        requires_negotiation = True

    # SHIPPING CALCULATION
    # Below 15 kg, show the admin-configured per-product delivery fees
    # even when the customer also has the option to negotiate delivery.
    if total_weight < Decimal("15"):

        for item in cart_items:

            fee = Decimal(
                str(
                    item.product_listing.fixed_shipping_fee
                    or 0
                )
            )

            # A fixed delivery fee is charged once per distinct product,
            # regardless of quantity. Heavy carts move to negotiation instead.
            product_id = item.product_listing.id
            if product_id not in charged_product_ids:
                shipping_fee += fee
                charged_product_ids.add(product_id)

    

    total = (
        subtotal
        + shipping_fee
    )
    return {

        "items": items_data,

        "subtotal": subtotal,

        "shipping": shipping_fee,

        "total": total,

        "total_weight": total_weight,

        "requires_shipping":
            requires_shipping,

        "requires_negotiation":
            requires_negotiation,
    }

def send_admin_negotiation_email(request, negotiation):

    subtotal = sum(
        item.get_total()
        for item in negotiation.items.all()
    )

    admin_url = request.build_absolute_uri(
        reverse(
            "approve_negotiation",
            args=[negotiation.pk]
        )
    )

    context = {
        "negotiation": negotiation,
        "subtotal": subtotal,
        "admin_url": admin_url,
    }

    html = render_to_string(
        "emails/admin_negotiation_request.html",
        context
)

    email = EmailMultiAlternatives(
        subject=f"Negotiation Request ({negotiation.code})",
        body="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.ADMIN_EMAIL]
    )

    email.attach_alternative(
        html,
        "text/html"
    )

    try:
        email.send()
    except smtplib.SMTPException as e:
        print("Email failed:", e)

def send_customer_quotation_email(request,negotiation):

    payment_url = request.build_absolute_uri(
        reverse(
            "pay_negotiation_secure",
            args=[negotiation.payment_token]
        )
    )

    subtotal = sum(
        item.get_total()
        for item in negotiation.items.all()
    )

    total = (
        subtotal +
        negotiation.shipping_fee
    )

    context = {

        "negotiation": negotiation,

        "payment_url": payment_url,

        "subtotal": subtotal,

        "total": total,
    }


    html = render_to_string(
        "emails/customer_quotation_ready.html",
        context
    )

    email = EmailMultiAlternatives(
        subject=f"Quotation Ready ({negotiation.code})",
        body="",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[negotiation.user.email]
    )

    email.attach_alternative(
        html,
        "text/html"
    )

    try:
        email.send()
    except smtplib.SMTPException as e:
        print("Email failed:", e)

def send_customer_negotiation_confirmation_email(request, negotiation):
    """Confirm the WhatsApp negotiation request to its current user."""
    recipient = getattr(negotiation.user, "email", "")
    if not recipient:
        return

    detail_url = request.build_absolute_uri(
        reverse("negotiation_detail", args=[negotiation.code])
    )
    EmailMultiAlternatives(
        subject=f"Negotiation Request Received ({negotiation.code})",
        body=(
            "We received your negotiation request and will send your "
            f"quotation shortly. Review its status here: {detail_url}"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    ).send(fail_silently=True)


def get_negotiation_total(negotiation):
    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += (
            item.get_price()
            *
            item.quantity
        )

    return (
        subtotal
        +
        negotiation.shipping_fee
    )

def generate_cart_signature(cart):
    data = []

    for item in cart.items.select_related(
        "product_listing"
    ).order_by("product_listing_id"):

        data.append(
            f"{item.product_listing_id}:{item.quantity}"
        )

    raw = "|".join(data)

    return hashlib.md5(raw.encode()).hexdigest()



