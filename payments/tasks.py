from celery import shared_task
from django.db import transaction
from orders.models import Order
from wallets.models import VendorWallet

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
        order.save(update_fields=["status"])
        for item in order.items.select_related("vendor"):
            wallet, _ = VendorWallet.objects.get_or_create(vendor=item.vendor)
            wallet.escrow_balance += item.escrow_amount
            wallet.save(update_fields=["escrow_balance"])
