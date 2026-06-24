from django.db import models
from accounts.models import Vendor
from orders.models import Order


class VendorWallet(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE)

    escrow_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.vendor.store_name


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(VendorWallet, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=10)  # credit / debit

    reference = models.CharField(max_length=100)
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)



class Commission(models.Model):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="commissions"
    )

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="commissions"
    )

    vendor = models.ForeignKey(
        "accounts.Vendor",
        on_delete=models.CASCADE,
        related_name="commissions"
    )

    product_commission = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_commission = models.DecimalField(max_digits=12, decimal_places=2)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)