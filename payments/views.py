from django.shortcuts import render, redirect

# Create your views here.
import requests
import uuid
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from orders.models import *
from django.http import JsonResponse
from cart.models import *


def initiate_payment(request):
    user = request.user
    cart = Cart.objects.get(user=user)
    items = cart.items.all()

    total = sum([
        item.product_listing.calculate_price() * item.quantity
        for item in items
    ])

    reference = str(uuid.uuid4())

    # CREATE ORDER FIRST
    order = Order.objects.create(
        customer=user,
        total_amount=total,
        reference=reference,
        status="pending"
    )

    url = "https://api.paystack.co/transaction/initialize"

    headers = {
        "Authorization":"Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba",
        "Content-Type": "application/json"
    }

    data = {
        "email": user.email,
        "amount": int(total * 100),
        "reference": reference,
        "callback_url": "http://127.0.0.1:8000/payment/verify/"
    }

    res = requests.post(url, json=data, headers=headers).json()

    # 🔥 SAFE CHECK
    if not res.get("data"):
        return JsonResponse({"error": res})

    return JsonResponse({
        "payment_url": res["data"]["authorization_url"]
    })

def payment_success(request):
    return render(request, "success.html")


def verify_payment(request):
    reference = request.GET.get("reference")

    url = f"https://api.paystack.co/transaction/verify/{reference}"

    headers = {
        "Authorization": "Bearer sk_test_6982814d5e1a9c3c49e4a7a434d84469247442ba"
    }

    res = requests.get(url, headers=headers).json()

    # 🔥 SAFETY CHECK
    if not res.get("data"):
        return redirect("payment_failed")

    if res["data"]["status"] == "success":

        order = Order.objects.get(reference=reference)

        # 🚨 PREVENT DOUBLE PROCESSING
        if order.status == "paid":
            return redirect("payment_success")

        order.status = "paid"
        order.save()

        cart = Cart.objects.get(user=order.customer)

        total = 0

        for item in cart.items.all():
            listing = item.product_listing
            price = listing.calculate_price()

            subtotal = price * item.quantity
            total += subtotal

            # ✅✅✅ STOCK REDUCTION (ONLY HERE)
            if listing.stock >= item.quantity:
                listing.stock -= item.quantity
                listing.save()
            else:
                return redirect("payment_failed")

            # 🔥 COMMISSION
            commission_rate = 0.10
            commission = int(subtotal) * int(commission_rate)
            escrow = int(subtotal) - int(commission)

            OrderItem.objects.create(
                order=order,
                product_listing=listing,
                vendor=listing.vendor,
                quantity=item.quantity,
                escrow_amount=escrow,
                commission=commission
            )

        order.total_amount = total
        order.save()

        # 🔥 CLEAR CART
        cart.items.all().delete()

        return redirect("payment_success")

    return redirect("payment_failed")
