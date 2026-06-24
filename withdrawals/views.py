import requests
from django.shortcuts import render, redirect

# Create your views here.
from django.conf import settings
from wallets.models import *
from .models import *

from decimal import Decimal

def request_withdrawal(request):

    vendor = request.user.vendor
    wallet = VendorWallet.objects.get(vendor=vendor)

    amount = wallet.balance

    if amount <= 0:
        return redirect("vendor_dashboard")

    WithdrawalRequest.objects.create(
        vendor=vendor,
        amount=amount
    )

    wallet.balance = 0
    wallet.save()

    WalletTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        type="debit",
        reference="withdrawal",
        description="Withdrawal request"
    )

    return redirect("vendor_dashboard")

def release_payment(order_item):

    if order_item.received and not order_item.released:

        wallet, _ = VendorWallet.objects.get_or_create(
            vendor=order_item.vendor
        )

        wallet.escrow_balance -= order_item.escrow_amount
        wallet.balance += order_item.escrow_amount
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=order_item.escrow_amount,
            type="credit",
            reference=order_item.order.reference,
            description="Escrow released"
        )

        order_item.released = True
        order_item.save()

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
    else:
        withdrawal.status = "failed"
        withdrawal.save()

    return redirect("admin_dashboard")


