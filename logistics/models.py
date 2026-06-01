import uuid
from django.db import models
# Create your models here.
from django.conf import settings
from orders.models import Order

class Hub(models.Model):
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()

    def __str__(self):
        return f"{self.name} - {self.city}"


class ShippingProvider(models.Model):
    name = models.CharField(max_length=100)  # GIGL, Sendbox
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ShippingOption(models.Model):
    provider = models.ForeignKey(ShippingProvider, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)  # Standard, Express
    delivery_min_days = models.IntegerField()
    delivery_max_days = models.IntegerField()

    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    per_kg_fee = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.provider.name} - {self.name}"


class Shipment(models.Model):

    STATUS = [
        ("created", "Created"),
        ("picked", "Picked Up"),
        ("in_transit", "In Transit"),
        ("at_hub", "At Hub"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("failed", "Failed Delivery"),
    ]

    order = models.ForeignKey( "orders.Order", on_delete=models.CASCADE, related_name="shipments")

    vendor = models.ForeignKey("accounts.Vendor", on_delete=models.CASCADE, null=True)

    tracking_id = models.CharField(max_length=100, unique=True)

    status = models.CharField(max_length=30, default="created")

    current_location = models.CharField(max_length=255, blank=True, null=True)

    delivery_agent_name = models.CharField(max_length=100, blank=True, null=True)

    delivery_agent_phone = models.CharField(max_length=20, blank=True, null=True)

    last_update = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)


class ShippingNegotiation(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("paid", "Paid"),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shipping_negotiations"
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    vat = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    shipping_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    final_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    locked_data = models.JSONField()

    admin_note = models.TextField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):

        if not self.code:
            self.code = f"NEG-{uuid.uuid4().hex[:8].upper()}"

        self.final_total = (
            self.subtotal +
            self.vat +
            self.shipping_fee
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.code  



