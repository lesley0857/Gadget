from celery import shared_task
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from orders.models import Order
from wallets.models import VendorWallet, WalletTransaction, Commission

@shared_task
def process_payment(data):
    metadata = data.get("metadata") or {}
    order_id, reference = metadata.get("order_id"), data.get("reference")
    if not order_id and not reference:
        return
    with transaction.atomic():
        queryset = Order.objects.select_for_update()
        order = queryset.filter(id=order_id).first() if order_id else queryset.filter(reference=reference).first()
        if not order or order.status == "paid" or (reference and order.reference != reference):
            return
        if data.get("status") != "success" or int(data.get("amount", 0)) != int(order.total_amount * 100):
            return
        order.status = "paid"
        order.amount_paid = order.total_amount
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "amount_paid", "paid_at"])
        for item in order.items.select_related("vendor", "product_listing"):
            item.status = "paid"
            item.save(update_fields=["status"])
            if item.vendor:
                wallet, _ = VendorWallet.objects.get_or_create(vendor=item.vendor)
                wallet.escrow_balance += item.escrow_amount
                wallet.save(update_fields=["escrow_balance"])

                WalletTransaction.objects.get_or_create(
                    wallet=wallet,
                    reference=order.reference,
                    defaults={
                        "amount": item.escrow_amount,
                        "type": "credit",
                        "description": f"Escrow hold for Order #{order.order_number or order.id} - {item.product_listing.name}"
                    }
                )

                Commission.objects.get_or_create(
                    order=order,
                    order_item=item,
                    vendor=item.vendor,
                    defaults={
                        "product_commission": item.commission,
                        "shipping_commission": Decimal("0.00"),
                        "total_commission": item.commission,
                    }
                )
