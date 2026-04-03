from django.db import models
from accounts.models import Vendor

class VendorWallet(models.Model):
    vendor = models.OneToOneField(Vendor, on_delete=models.CASCADE)
    escrow_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

class WalletTransaction(models.Model):
    wallet = models.ForeignKey(VendorWallet, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
