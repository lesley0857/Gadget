from django.db import models
from accounts.models import User, Vendor
from catalog.models import *

class Order(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

class OrderItem(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
    ]
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product_listing = models.ForeignKey(ProductListing, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)

    quantity = models.PositiveIntegerField()
    escrow_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2)
    delivered_at = models.DateTimeField(null=True, blank=True)
    released = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="pending")
