import requests
from django.shortcuts import render, redirect

# Create your views here.
from django.conf import settings
from wallets.models import *
from .models import *


def request_withdrawal(request):
    vendor = request.user.vendor
    wallet = VendorWallet.objects.get(vendor=vendor)

    amount = wallet.balance

    WithdrawalRequest.objects.create(
        vendor=vendor,
        amount=amount
    )

    wallet.balance = 0
    wallet.save()

    return redirect("vendor_dashboard")


def release_payment(item):
    if item.received and not item.released:

        wallet, _ = VendorWallet.objects.get_or_create(
            vendor=item.vendor
        )

        wallet.balance += item.escrow_amount
        wallet.save()

        item.released = True
        item.save()


def approve_withdrawal(request, withdrawal_id):
    withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)

    vendor = withdrawal.vendor

    url = "https://api.paystack.co/transfer"

    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "source": "balance",
        "amount": int(withdrawal.amount * 100),
        "recipient": vendor.recipient_code,
        "reason": "Vendor payout"
    }

    res = requests.post(url, json=data, headers=headers).json()

    if res.get("status"):
        withdrawal.status = "paid"
        withdrawal.save()

    return redirect("admin_dashboard")