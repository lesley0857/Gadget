from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from orders.models import OrderItem
from disputes.models import Dispute
from wallets.models import VendorWallet

@shared_task
def auto_release_escrow():
    cutoff = timezone.now() - timedelta(days=3)

    items = OrderItem.objects.filter(
        delivered_at__lte=cutoff,
        released=False
    )

    for item in items:
        if not Dispute.objects.filter(order_item=item, status="open").exists():
            wallet = VendorWallet.objects.get(vendor=item.vendor)
            wallet.escrow_balance -= item.escrow_amount
            wallet.available_balance += item.escrow_amount
            wallet.save()

            item.released = True
            item.save()
