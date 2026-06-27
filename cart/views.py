
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

        price = listing.final_price()
        subtotal = price * quantity

        cart_items_data.append({
            "id": listing.id,
            "name": listing.name,
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
            price = listing.final_price()
            subtotal = price * item.quantity

            cart_items_data.append({
                "id": listing.id,
                "name": listing.name,
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
            price = listing.final_price()
            subtotal = price * item["quantity"]

            cart_items_data.append({
                "id": listing.id,
                "name": listing.name,
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
def negotiate_cart(request,negotiation_type="cart"):

    cart = get_object_or_404(
        Cart,
        user=request.user
    )

    profile, created = (
        UserProfile.objects.get_or_create(
            user=request.user
        )
    )
    if not profile.phone:
        messages.error(
            request,
            "Please update your phone number first."
        )
        return redirect("profile")
    signature = generate_cart_signature(cart)
    active_negotiation = (
            NegotiationRequest.objects
            .filter(
                user=request.user,
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
            user=request.user,
            status="pending"
        ).exclude(
            cart_signature=signature
        ).update(
            status="expired"
        )

    if active_negotiation:
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
    negotiation = NegotiationRequest.objects.create(
        user=request.user,
        negotiation_type=negotiation_type,
        customer_name=f"{profile.first_name} {profile.last_name}",
        customer_email=request.user.email,
        customer_phone=profile.phone,

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

# Admin is deirect here from email. 
# can also edit prices and delivery here
# http://127.0.0.1:8000/admin-negotiation/17/
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

    total = subtotal + negotiation.shipping_fee

    payment_reference = f"NEG-{uuid.uuid4().hex[:12]}"

    negotiation.payment_reference = payment_reference
    negotiation.save()


    callback_url = request.build_absolute_uri(
        reverse(
            "verify_negotiated_payment",
        )
    )
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
    print(PAYSTACK_SECRET_KEY)
    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": negotiation.user.email,
            "amount": int(total * 100),
            "reference": payment_reference,
            "callback_url":callback_url
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
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
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
        negotiation=negotiation,
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
            "total": total,
            "subtotal":subtotal
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
    subtotal = sum(
        i.get_total()
        for i in negotiation.items.all()
    )
    total += negotiation.shipping_fee
    return render(request,"users_negotiation_view.html",
        {
            'negotiation':negotiation,
            'subtotal':subtotal,
            'total':total
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
            print('save')
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
        status= "processing",
        created_at__lt=timezone.now()-timedelta(hours=1)
    ).update(status="cancelled")

    # =========================
    # SAFE SHIPPING EXTRACTION
    # =========================
    shipping_options = data.get("shipping_options") or []

    # =========================
    # CONTEXT (NO OVERWRITES)
    # =========================
    context = {

    "items": cart.items.all(),

    "subtotal": data["subtotal"],

    "shipping": data["shipping"],

    "total": data["total"],

    "paystack_amount":
        int(data["total"] * 100),

    "requires_negotiation":
        data["requires_negotiation"],
    }
    print("VIEW NEGOTIATION:",data["requires_negotiation"])

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