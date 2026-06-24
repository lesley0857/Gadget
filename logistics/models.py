import uuid
from django.db import models
# Create your models here.
from django.conf import settings
from orders.models import Order

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



    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="shipments",
    )

    provider = models.CharField(
        max_length=100
    )

    pickup_address = models.TextField()

    delivery_address = models.TextField()

    tracking_id = models.CharField(
        max_length=100,
        unique=True,
    )

    estimated_delivery = models.DateField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS,
        default="created",
    )

    current_location = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    courier_name = models.CharField(
        max_length=100,
        blank=True,
    )

    delivery_agent_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    delivery_agent_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    last_update = models.DateTimeField(
        auto_now=True,
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):

        return f"{self.tracking_id}"

class ShipmentUpdate(models.Model):

    STATUS = [
        ("created", "Created"),
        ("picked", "Picked Up"),
        ("in_transit", "In Transit"),
        ("at_hub", "At Hub"),
        ("out_for_delivery", "Out for Delivery"),
        ("delivered", "Delivered"),
        ("failed", "Failed Delivery"),
    ]

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="updates"
    )

    status = models.CharField(
        max_length=50,
        choices=STATUS
    )

    message = models.TextField()

    location = models.CharField(
        max_length=255,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["created_at"]
    def __str__(self):
        return (
            f"{self.shipment.tracking_id}"
            f" - "
            f"{self.status}"
        )

