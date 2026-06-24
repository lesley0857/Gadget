from django.db import models

# Create your models here.
from accounts.models import *


class WithdrawalRequest(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    STATUS = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("rejected", "Rejected"),
    ]
    status = models.CharField(max_length=20, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)


