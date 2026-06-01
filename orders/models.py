from django.db import models
from accounts.models import User
from catalog.models import *
from django.conf import settings

class Order(models.Model):
    STATUS_CHOICES=[
        ("pending", "Pending"),
        ("processing", "Processing"),  # 🔒 locked
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ],
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    shipping_city = models.CharField(max_length=100)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES[0], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    payment_url = models.URLField(null=True, blank=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)

    billing_address = models.TextField()
    shipping_address = models.TextField()

    locked_data = models.JSONField(null=True, blank=True)


    def __str__(self):
        return f"{self.pk}--{self.customer.email}--{self.total_amount}--{self.status}--{self.created_at.date()}--{self.created_at.time()}"

class OrderItem(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product_listing = models.ForeignKey("catalog.ProductListing", on_delete=models.CASCADE)
    vendor = models.ForeignKey("accounts.Vendor", on_delete=models.PROTECT)

    quantity = models.PositiveIntegerField()
    escrow_amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission = models.DecimalField(max_digits=12, decimal_places=2)
    delivered_at = models.DateTimeField(null=True, blank=True)
    released = models.BooleanField(default=False)
    received = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="pending")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    delivery_start = models.DateTimeField(null=True, blank=True)
    delivery_end = models.DateTimeField(null=True, blank=True)

    