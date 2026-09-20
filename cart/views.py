
# Create your views here.
import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem
from catalog.models import ProductListing
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_POST
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .utils import *
from cart.models import Cart
from orders.models import *
from decimal import Decimal
from accounts.models import UserProfile
from django.urls import reverse
from urllib.parse import quote
from django.contrib import messages
import uuid
import requests
from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from logistics.models import Shipment, ShipmentUpdate
from .models import NegotiationRequest
from django.db.models import Q
from django.contrib.admin.views.decorators import staff_member_required
from pricing.services import calculate_checkout_pricing



def add_to_cart(request, listing_id):

    if request.method == "POST":

        try:
            quantity = max(1, int(request.POST.get("quantity", 1)))
        except (TypeError, ValueError):
            return JsonResponse({
                "success": False,
                "error": "Quantity must be a positive whole number."
            }, status=400)

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
                item.quantity += quantity
                item.save()

            items = cart.items.all()

            for i in items:

                price = i.product_listing.final_price()
                subtotal = price * i.quantity

                image = ""

                media = i.product_listing.media.filter(
                    is_primary=True
                ).first()

                if media:
                    image = media.file.url

                cart_items_data.append({
                    "id": i.product_listing.id,
                    "name": i.product_listing.name,
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

                cart[str(listing_id)]["quantity"] += quantity

            else:

                cart[str(listing_id)] = {
                    "quantity": quantity
                }

            request.session["cart"] = cart
            request.session.modified = True

            # REBUILD RESPONSE
            for id, item in cart.items():

                p = ProductListing.objects.get(id=id)

                quantity = item["quantity"]

                price = p.final_price()

                subtotal = price * quantity

                image = ""

                media = p.media.filter(
                    is_primary=True
                ).first()

                if media:
                    image = media.file.url

                cart_items_data.append({
                    "id": p.id,
                    "name": p.name,
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
            total_price = listing.final_price() * quantity

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

    if not listing_id or action not in {"increment", "decrement", "remove"}:
        return JsonResponse({
            "success": False,
            "error": "Invalid cart update request."
        }, status=400)
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)

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
        request.session.modified = True

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

        price = listing.final_price()
        subtotal = price * quantity

        cart_items_data.append({
            "id": listing.id,
            "name": listing.name,
            "price": float(price),
            "quantity": quantity,
            "subtotal": float(subtotal),
            "shipping_fee": float(listing.fixed_shipping_fee or 0),
            "image": listing.media.first().file.url if listing.media.exists() else ""
        })

        total += subtotal
    checkout_data = build_vendor_checkout(request.user) if request.user.is_authenticated else build_vendor_checkout(session_cart=request.session.get("cart", {}))
    cart_count = len(cart_items_data)
    return JsonResponse({
        "success": True,
        "cart_items": cart_items_data,
        "subtotal": float(checkout_data["subtotal"]),
        "shipping": float(checkout_data["shipping"]),
        "total": float(checkout_data["total"]),
        "cart_count":cart_count,
    })

def cart_summary(request):
    """Return side-cart lines plus delivery totals using the checkout rules."""
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        source_items = [(row.product_listing, row.quantity) for row in cart.items.select_related("product_listing").prefetch_related("product_listing__media").all()] if cart else []
    else:
        source_items = []
        for listing_id, row in request.session.get("cart", {}).items():
            listing = ProductListing.objects.filter(pk=listing_id).prefetch_related("media").first()
            if listing:
                source_items.append((listing, max(1, int(row.get("quantity", 1)))))

    subtotal = Decimal("0.00")
    total_weight = Decimal("0.00")
    charged_product_ids = set()
    shipping = Decimal("0.00")
    lines = []
    for listing, quantity in source_items:
        unit_price = Decimal(str(listing.final_price()))
        line_total = unit_price * quantity
        weight = Decimal(str(listing.weight or 0)) * quantity
        media = listing.media.filter(is_primary=True).first() or listing.media.first()
        lines.append({
            "id": listing.id, "name": listing.name, "price": float(unit_price),
            "quantity": quantity, "subtotal": float(line_total),
            "shipping_fee": float(listing.fixed_shipping_fee or 0),
            "shipping_weight": float(weight),
            "image": media.file.url if media else "",
        })
        subtotal += line_total
        total_weight += weight

    if total_weight < Decimal("15"):
        for listing, _ in source_items:
            if listing.id not in charged_product_ids:
                shipping += Decimal(str(listing.fixed_shipping_fee or 0))
                charged_product_ids.add(listing.id)

    pricing = calculate_checkout_pricing(subtotal=subtotal, shipping=shipping)

    return JsonResponse({
        "cart_items": lines, "cart_count": len(lines), "subtotal": float(subtotal),
        "shipping": float(shipping), "total": float(pricing.total),
    })
def negotiate_cart(request,negotiation_type="cart"):

    user = request.user
    if not user.is_authenticated:
        from accounts.models import User
        guest_id = uuid.uuid4().hex
        user = User.objects.create_user(username=f"guest-neg-{guest_id}", email=f"guest-neg-{guest_id}@checkout.remarobe.invalid")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        cart = Cart.objects.create(user=user)
        for listing_id, row in request.session.get("cart", {}).items():
            listing = ProductListing.objects.filter(pk=listing_id).first()
            if listing:
                CartItem.objects.create(cart=cart, product_listing=listing, quantity=max(1, int(row.get("quantity", 1))))
    else:
        cart = get_object_or_404(Cart, user=user)

    profile, created = UserProfile.objects.get_or_create(user=user)
    # Billing-form details are accepted for guest negotiation requests.
    profile.first_name = request.POST.get("first_name", profile.first_name)
    profile.last_name = request.POST.get("last_name", profile.last_name)
    profile.phone = request.POST.get("shipping_phone", request.POST.get("phone", profile.phone))
    profile.address = request.POST.get("shipping_address", request.POST.get("address", profile.address))
    profile.city = request.POST.get("shipping_city", request.POST.get("city", profile.city))
    profile.state = request.POST.get("shipping_state", request.POST.get("state", profile.state))
    profile.save()
    if request.POST.get("email"):
        user.email = request.POST["email"]
        user.save(update_fields=["email"])

    shipping_fee_raw = request.POST.get("shipping_fee") or request.POST.get("shipping") or 0
    try:
        shipping_fee_val = Decimal(str(shipping_fee_raw))
    except (TypeError, ValueError, Exception):
        shipping_fee_val = Decimal("0.00")

    if not profile.phone:
        messages.error(
            request,
            "Please update your phone number first."
        )
        return redirect("update_profile")
    signature = generate_cart_signature(cart)
    active_negotiation = (
            NegotiationRequest.objects
            .filter(
                user=user,
                cart_signature=signature,
                status__in=[
                    "pending",
                    "quoted"
                ]
            )
            .order_by("-created_at")
            .first()
        )  
    # set to expired when cart has same items and pending neotiations
    NegotiationRequest.objects.filter(
            user=user,
            status="pending"
        ).exclude(
            cart_signature=signature
        ).update(
            status="expired"
        )

    if active_negotiation:
        if shipping_fee_val > 0:
            active_negotiation.shipping_fee = shipping_fee_val
            active_negotiation.save(update_fields=["shipping_fee"])
        messages.warning(
        request,
        (
            f"You already have an active negotiation "
            f"({active_negotiation.code})."
        )
    )
        return redirect(
            "negotiation_detail",
            code=active_negotiation.code
        )

    negotiation_type = request.GET.get(
        "type",
        "cart"
    )
    full_address = ", ".join(filter(None, [profile.address, profile.city, profile.state]))
    negotiation = NegotiationRequest.objects.create(
        user=user,
        negotiation_type=negotiation_type,
        customer_name=f"{profile.first_name} {profile.last_name}".strip(),
        customer_email=user.email,
        customer_phone=profile.phone,
        shipping_address=full_address,
        shipping_fee=shipping_fee_val,
        cart_signature=signature,
    )

    whatsapp_lines = []

    for item in cart.items.select_related(
        "product_listing"
    ):

        price = item.product_listing.final_price()

        NegotiationItem.objects.create(

            negotiation=negotiation,

            product_listing=item.product_listing,

            quantity=item.quantity,

            original_price=price
        )

        whatsapp_lines.append(
            f"{item.product_listing.name}"
            f" | Qty:{item.quantity}"
            f" | ₦{price:,.2f}"
        )

    send_admin_negotiation_email(
        request,
        negotiation
    )
    send_customer_negotiation_confirmation_email(
        request,
        negotiation
    )

    message = f"""

    Hello Remarobe,

    Negotiation Request

    Code:
    {negotiation.code}

    Customer:
    {request.user.get_full_name()}

    Phone:
    {profile.phone}

    Items:

    {chr(10).join(whatsapp_lines)}
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
        negotiation = NegotiationRequest.objects.filter(
            code=code
        ).first()
        if negotiation:
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

# Admin is deirect here from email. 
# can also edit prices and delivery here
# http://127.0.0.1:8000/admin-negotiation/17/
@transaction.atomic
@login_required
def approve_negotiation(request,pk):
    negotiation = get_object_or_404(
        NegotiationRequest,
        pk=pk
    )

    if request.method == "POST":

        shipping = Decimal(
            request.POST.get(
                "shipping_fee",
                0
            )
        )
        
        negotiation.shipping_fee = shipping
        
        negotiation.status = "quoted"

        negotiation.payment_link_expires_at = (

            timezone.now()
            +
            timedelta(hours=12)
        )

        negotiation.save()

        for item in negotiation.items.all():

            if negotiation.negotiation_type == "shipping":

                item.negotiated_price = (
                    item.original_price
                )

            else:

                price = request.POST.get(
                    f"price_{item.id}"
                )
                quantity = request.POST.get(
                    f"qty_{item.id}"
                )

                item.negotiated_price = Decimal(price)
                if quantity:
                    item.quantity = int(quantity)
                    item.save()
            item.save()
        send_customer_quotation_email(
            request,
            negotiation
        )

        messages.success(
            request,
            "Quotation approved and sent."
        )

        return redirect(
            "approve_negotiation",
            pk=pk
        )

    return render(
        request,
        "approve_negotiation.html",
        {
            "negotiation": negotiation
        }
    )

@transaction.atomic
def pay_negotiation(request, code):

    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )

    if negotiation.status == "paid":
        messages.success( request, "Quotation already paid." )
        return redirect( "payment_success" )

    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += (
            item.negotiated_price *
            item.quantity
        )

    shipping = negotiation.shipping_fee or Decimal("0.00")
    pricing = calculate_checkout_pricing(
        subtotal=subtotal,
        shipping=shipping
    )

    payment_reference = f"NEG-{uuid.uuid4().hex[:12]}"

    negotiation.payment_reference = payment_reference
    negotiation.save()


    callback_url = request.build_absolute_uri(
        reverse(
            "verify_negotiated_payment",
        )
    )
    PAYSTACK_SECRET_KEY = getattr(settings, "PAYSTACK_SECRET_KEY", None) or os.getenv("PAYSTACK_SECRET_KEY")
    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": negotiation.user.email,
            "amount": pricing.paystack_amount_kobo,
            "reference": payment_reference,
            "callback_url": callback_url
        },
        headers={
            "Authorization":
                f"Bearer {PAYSTACK_SECRET_KEY}"
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

@transaction.atomic
@login_required
def pay_negotiation_secure(request,token):

    negotiation = get_object_or_404(
        NegotiationRequest,
        payment_token=token
    )
    if negotiation.status == "paid":

        messages.error(
            request,
            "This quotation has already been paid."
        )

        return redirect("home")
    
    if (
        not negotiation.payment_link_expires_at
    ):
        return redirect(
            "quotation_expired"
        )

    if (
        timezone.now()
        >
        negotiation.payment_link_expires_at
    ):

        negotiation.status = "expired"

        negotiation.save()

        return redirect(
            "quotation_expired"
        )

    return pay_negotiation(
            request,
            negotiation.code
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
    PAYSTACK_SECRET_KEY = getattr(settings, "PAYSTACK_SECRET_KEY", None) or os.getenv("PAYSTACK_SECRET_KEY")
    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers={
            "Authorization":
                f"Bearer {PAYSTACK_SECRET_KEY}"
        }
    )

    paystack_data = response.json()

    if (not paystack_data.get("status") or paystack_data["data"]["status"] != "success"):
        return JsonResponse({
            "error":
            "Payment verification failed"
        })

    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += item.get_total()

    shipping = negotiation.shipping_fee or Decimal("0.00")
    pricing = calculate_checkout_pricing(
        subtotal=subtotal,
        shipping=shipping
    )

    order = Order.objects.create(
        customer=negotiation.user,
        total_amount=pricing.total,
        amount_before_gateway_fee=pricing.net_total,
        gateway_fee=pricing.gateway_fee,
        amount_paid=pricing.total,
        email = negotiation.user.email,
        phone = negotiation.customer_phone,
        shipping_amount=pricing.shipping,
        shipping_fee=pricing.shipping,
        subtotal=pricing.subtotal,
        reference=reference,
        negotiation=negotiation,
        status="paid",
        paid_at=timezone.now(),
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

    tracking_id = (f"TRK-{uuid.uuid4().hex[:10].upper()}")

    shipment = Shipment.objects.create(

        order=order,

        provider="Remarobe Logistics",

        pickup_address=
            "Remarobe Warehouse",

        delivery_address=
            order.shipping_address,

        tracking_id=
            tracking_id,

        status="created"
    )
    ShipmentUpdate.objects.create(

        shipment=shipment,

        status="created",

        message=
            "Shipment created."
    )
    return redirect(
        "payment_success"
    )


@login_required
def negotiation_detail(request, code):

    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )
    subtotal = sum(
        i.get_total()
        for i in negotiation.items.all()
    )
    shipping_fee = negotiation.shipping_fee or Decimal("0.00")
    pricing = calculate_checkout_pricing(
        subtotal=subtotal,
        shipping=shipping_fee
    )

    return render(
        request,
        "negotiation_detail.html",
        {
            "negotiation": negotiation,
            "total": pricing.total,
            "subtotal": subtotal,
            "shipping": shipping_fee,
        }
    )

@login_required
def user_negotiation_ready_view(request,code):
    negotiation = get_object_or_404(
        NegotiationRequest,
        code=code
    )
    subtotal = sum(
        i.get_total()
        for i in negotiation.items.all()
    )
    shipping_fee = negotiation.shipping_fee or Decimal("0.00")
    pricing = calculate_checkout_pricing(
        subtotal=subtotal,
        shipping=shipping_fee
    )
    return render(request,"users_negotiation_view.html",
        {
            'negotiation': negotiation,
            'subtotal': subtotal,
            'shipping': shipping_fee,
            'total': pricing.total
        }
    )


def quotation_expired(request):

    return render(
        request,
        "quotation_expired.html"
    )

# for Admin
@staff_member_required
def negotiation_dashboard(request):


    status = request.GET.get(
        "status",
        ""
    )

    search = request.GET.get(
        "search",
        ""
    )

    negotiations = (
        NegotiationRequest.objects
        .select_related(
            "user",
            "order"
        )
        .prefetch_related(
            "items"
        )
        .order_by(
            "-created_at"
        )
    )

    if status:

        negotiations = negotiations.filter(
            status=status
        )

    if search:

        negotiations = negotiations.filter(

            Q(code__icontains=search)

            |

            Q(customer_name__icontains=search)

            |

            Q(customer_email__icontains=search)

            |

            Q(customer_phone__icontains=search)
        )

    pending_count = (
        NegotiationRequest.objects.filter(
            status="pending"
        ).count()
    )

    quoted_count = (
        NegotiationRequest.objects.filter(
            status="quoted"
        ).count()
    )

    paid_count = (
        NegotiationRequest.objects.filter(
            status="paid"
        ).count()
    )

    context = {

        "negotiations":
            negotiations,

        "pending_count":
            pending_count,

        "quoted_count":
            quoted_count,

        "paid_count":
            paid_count,

        "current_status":
            status,

        "search":
            search,
    }

    return render(
        request,
        "admin_negotiation_dashboard.html",
        context
    )

# Admin can edit prices and delivery fee here
# http://127.0.0.1:8000/admin-negotiation/17/
@staff_member_required
def admin_negotiation_detail(request, pk):
    negotiation = get_object_or_404(
        NegotiationRequest,
        pk=pk
    )

    # ===================================
    # SAVE QUOTE
    # ===================================

    if request.method == "POST":

        action = request.POST.get(
            "action"
        )

        # -------------------------
        # SAVE PRICES
        # -------------------------

        if action == "save_quote":
            for item in negotiation.items.all():

                value = request.POST.get(
                    f"price_{item.id}"
                )
                quantity = request.POST.get(
                    f"qty_{item.id}"
                )

                if value:
                    item.negotiated_price = Decimal(
                        value
                    ) 
                    item.save()
                if quantity:
                    item.quantity = int(quantity)

                    item.save()

            shipping_fee = request.POST.get(
                "shipping_fee"
            )

            negotiation.shipping_fee = Decimal(
                shipping_fee or 0
            )

            negotiation.save()

            messages.success(
                request,
                "Quote updated successfully."
            )

            return redirect(
                "admin_negotiation_detail",
                negotiation.pk
            )

        # -------------------------
        # GENERATE QUOTE
        # -------------------------

        elif action == "generate_quote":

            shipping_fee = request.POST.get(
                "shipping_fee"
            )

            negotiation.shipping_fee = Decimal(
                shipping_fee or 0
            )

            negotiation.status = "quoted"

            negotiation.payment_link_expires_at = (
                timezone.now()
                + timedelta(days=7)
            )

            negotiation.save()

            send_customer_quotation_email(
                request,
                negotiation
            )

            messages.success(
                request,
                "Quotation generated and sent."
            )

            return redirect(
                "admin_negotiation_detail",
                negotiation.pk
            )
        elif action == "send_payment_link":

            if negotiation.status != "quoted":

                messages.error(
                    request,
                    "Generate quote first."
                )

                return redirect(
                    "admin_negotiation_detail",
                    negotiation.pk
                )

            send_customer_quotation_email(
                request,
                negotiation
            )

            messages.success(
                request,
                "Payment link sent."
            )

            return redirect(
                "admin_negotiation_detail",
                negotiation.pk
            )
        
        
    # ===================================
    # TOTALS
    # ===================================

    subtotal = Decimal("0.00")

    for item in negotiation.items.all():

        subtotal += item.get_total()

    total = (
        subtotal
        + negotiation.shipping_fee
    )

# ===================================
# SHIPMENT
# ===================================

    shipment = None

    if negotiation.order:

        shipment = Shipment.objects.filter(
            order=negotiation.order
        ).first()

    context = {

        "negotiation": negotiation,

        "subtotal": subtotal,

        "total": total,

        "shipment": shipment,
    }

    return render(
        request,
        "admin_negotiation_detail.html",
        context
    )

@transaction.atomic
def checkout_view(request):
    """Checkout is deliberately available without an account."""
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        items = list(cart.items.select_related("product_listing").prefetch_related("product_listing__media")) if cart else []
        data = build_vendor_checkout(request.user) if items else {"subtotal": 0, "shipping": 0, "total": 0, "requires_negotiation": False}
    else:
        session_cart = request.session.get("cart", {})
        items = []
        for listing_id, row in session_cart.items():
            listing = ProductListing.objects.filter(pk=listing_id).prefetch_related("media").first()
            if listing:
                items.append(type("GuestCartItem", (), {"product_listing": listing, "quantity": max(1, int(row.get("quantity", 1))), "get_total_price": lambda item: item.product_listing.final_price() * item.quantity})())
        data = build_vendor_checkout(session_cart=session_cart) if items else {"subtotal": 0, "shipping": 0, "total": 0, "requires_negotiation": False}
    cart_product_ids = [item.product_listing.id for item in items]
    category_ids = set()
    for item in items:
        product = item.product_listing
        item.shipping_fee = product.fixed_shipping_fee or Decimal("0.00")
        item.fixed_shipping_fee = item.shipping_fee
        item.shipping_type = product.shipping_type
        item.weight = product.weight or Decimal("0.00")
        item.name = product.name
        item.display_name = product.name
        item.unit_price = product.final_price()
        item.price = item.unit_price
        item.line_total = item.unit_price * item.quantity
        item.subtotal = item.line_total
        media_items = list(product.media.all())
        media = next((entry for entry in media_items if entry.is_primary), None) or (media_items[0] if media_items else None)
        try:
            item.media_url = media.file.url if (media and media.file) else ""
        except (ValueError, Exception):
            item.media_url = ""
        item.media_type = media.media_type if media else ""
        category_ids.update(product.categories.values_list("id", flat=True))
    related_products = list(ProductListing.objects.filter(
        is_active=True, categories__id__in=category_ids
    ).exclude(id__in=cart_product_ids).prefetch_related("media", "categories").distinct().order_by("-id")[:4])
    if len(related_products) < 4:
        existing_ids = cart_product_ids + [p.id for p in related_products]
        fallback_products = list(ProductListing.objects.filter(
            is_active=True
        ).exclude(id__in=existing_ids).prefetch_related("media", "categories").distinct().order_by("-id")[:4 - len(related_products)])
        related_products.extend(fallback_products)
    for product in related_products:
        media_items = list(product.media.all())
        media = next((entry for entry in media_items if entry.is_primary), None) or (media_items[0] if media_items else None)
        try:
            product.display_media_url = media.file.url if (media and media.file) else ""
        except (ValueError, Exception):
            product.display_media_url = ""
        product.display_media_type = media.media_type if media else ""
    shipping_details = {}
    customer_lat = None
    customer_lon = None
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        shipping_details = {"first_name": profile.first_name, "last_name": profile.last_name, "email": request.user.email, "phone": profile.phone, "address": profile.address, "city": profile.city, "state": profile.state}
        customer_lat = profile.latitude
        customer_lon = profile.longitude

    # Collect unique vendors in cart for logistics fee calculation
    from accounts.models import Vendor as VendorModel
    vendor_ids = [item.product_listing.vendor_id for item in items if hasattr(item.product_listing, "vendor_id")]
    vendors_in_cart = list(VendorModel.objects.filter(pk__in=set(vendor_ids)))

    return render(request, "checkout.html", {
        **data,
        "items": items,
        "paystack_amount": int(data["total"] * 100),
        "related_products": related_products,
        "shipping_details": shipping_details,
        "customer_lat": customer_lat or "",
        "customer_lon": customer_lon or "",
        "has_vendors_with_coords": any(v.latitude for v in vendors_in_cart),
    })


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