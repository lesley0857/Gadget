from celery import shared_task
from orders.models import Order
from wallets.models import VendorWallet

@shared_task
def process_payment(data):
    order_id = data["metadata"]["order_id"]
    order = Order.objects.get(id=order_id)
    order.status = "paid"
    order.save()

    for item in order.items.all():
        wallet, _ = VendorWallet.objects.get_or_create(vendor=item.vendor)
        wallet.escrow_balance += item.escrow_amount
        wallet.save()
