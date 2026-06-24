# logistics/utils.py

from urllib.parse import quote

from django.conf import settings
from decimal import Decimal
from django.core.mail import EmailMultiAlternatives

from django.template.loader import render_to_string

from django.urls import reverse


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
₦{data['subtotal']}

Please review this request.

"""

    whatsapp_number = "2348100911189"

    return (

        f"https://wa.me/{whatsapp_number}"

        f"?text={quote(message)}"

    )


def send_shipping_negotiation_email(

    request,

    negotiation,

):
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

            reverse(

                "admin:index"

            )

        )
    )

    context = {

        "negotiation": negotiation,
        "subtotal": subtotal,
        "admin_url": admin_url,
        "detail_url": detail_url,

    }

    #
    # EMAIL TO ADMIN
    #

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

    admin_email_message.attach_alternative(

        admin_html,

        "text/html",

    )

    admin_email_message.send()

    #
    # EMAIL TO CUSTOMER
    #

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

    customer_email.attach_alternative(

        customer_html,

        "text/html",

    )

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





