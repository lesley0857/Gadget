from django.shortcuts import render,redirect
import requests
import json
import uuid
from django.conf import settings
# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import OrderCreateSerializer

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from decimal import Decimal

from cart.utils import build_vendor_checkout

from django.http import JsonResponse
from .models import Order
from logistics.models import *

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response({"order_id": order.id})


@login_required
def user_orders_json(request):

    orders = Order.objects.filter(customer=request.user).prefetch_related("items")

    data = []

    for order in orders:
        for item in order.items.all():

            listing = item.product_listing   # ✅ FIX HERE

            # IMAGE
            image = ""
            if listing.media.exists():
                image = listing.media.first().file.url

            data.append({
                "id": item.id,
                "name": listing.product.name,   # ✅ FIX
                "status": order.status,
                "quantity": item.quantity,
                "price": float(item.escrow_amount),
                "image": image
            })

    return JsonResponse({
        "success": True,
        "orders": data
    })

@login_required
@require_POST
def request_shipping_negotiation(request):

    user = request.user

    data = build_vendor_checkout(user)

    negotiation = ShippingNegotiation.objects.create(
        customer=user,

        subtotal=Decimal(data["subtotal"]),
        vat=Decimal(data["vat"]),

        shipping_fee=Decimal("0.00"),

        locked_data=data
    )

    return JsonResponse({
        "success": True,
        "code": negotiation.code,
        "message": (
            "Negotiation request created."
        )
    })

@login_required
def negotiated_checkout(request, code):

    negotiation = get_object_or_404(
        ShippingNegotiation,
        code=code,
        customer=request.user
    )

    if negotiation.status != "approved":
        return JsonResponse({
            "error": "Negotiation not approved yet"
        }, status=400)

    data = negotiation.locked_data

    context = {
        "negotiation": negotiation,
        "vendors_data": data["vendors_data"],

        "subtotal": negotiation.subtotal,
        "vat": negotiation.vat,
        "shipping": negotiation.shipping_fee,
        "total": negotiation.final_total,

        "negotiated": True
    }

    return render(
        request,
        "negotiated_checkout.html",
        context
    )


@login_required
def pay_negotiated_shipping(request, code):

    negotiation = get_object_or_404(
        ShippingNegotiation,
        code=code,
        customer=request.user
    )

    if negotiation.status != "approved":
        return JsonResponse({
            "error": "Negotiation not approved"
        }, status=400)

    reference = str(uuid.uuid4())

    order = Order.objects.create(
        customer=request.user,

        total_amount=negotiation.final_total,

        subtotal=negotiation.subtotal,
        vat_amount=negotiation.vat,
        shipping_amount=negotiation.shipping_fee,

        reference=reference,

        status="processing",

        locked_data=json.dumps(
            negotiation.locked_data
        ),

        billing_address=request.user.userprofile.address,
        shipping_address=request.user.userprofile.address,

        phone=request.user.userprofile.phone,
    )

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        json={
            "email": request.user.email,
            "amount": int(
                negotiation.final_total * 100
            ),
            "reference": reference,
            "callback_url":
                "http://127.0.0.1:8000/payment/verify/"
        },
        headers={
            "Authorization":
                "Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
        }
    )

    res = response.json()

    if not res.get("status"):

        order.status = "cancelled"
        order.save()

        return JsonResponse({
            "error": res.get("message")
        })

    order.payment_url = (
        res["data"]["authorization_url"]
    )

    order.save()

    negotiation.status = "paid"
    negotiation.save()

    return redirect(order.payment_url)