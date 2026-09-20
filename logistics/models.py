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



    order = models.ForeignKey("orders.Order",on_delete=models.CASCADE,related_name="shipments",)
    provider = models.CharField(max_length=100)
    pickup_address = models.TextField()
    delivery_address = models.TextField()
    tracking_id = models.CharField(max_length=100,unique=True,)
    estimated_delivery = models.DateField(null=True,blank=True,)
    status = models.CharField(
        max_length=30,
        choices=STATUS,
        default="created",db_index=True
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
    class Meta:
        indexes = [models.Index(fields=["tracking_id"]),
                models.Index(fields=["status"]),]
    
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



class LogisticsRate(models.Model):
    """
    Admin-configurable tiered delivery rate.
    The system picks the most specific active row whose
    min_km <= distance < max_km (or max_km is None for unlimited).
    """

    label = models.CharField(
        max_length=100,
        help_text="Friendly name, e.g. 'Local (0-20 km)'"
    )

    min_km = models.PositiveIntegerField(
        default=0,
        help_text="Lower bound of distance band (inclusive, km)"
    )

    max_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Upper bound (exclusive, km). Leave blank for unlimited."
    )

    base_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500,
        help_text="Flat fee charged regardless of distance (N)"
    )

    rate_per_km = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=50,
        help_text="Additional fee per km (N)"
    )

    weight_rate_per_kg = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=30,
        help_text="Extra fee per kg above the free weight threshold (N)"
    )

    free_weight_kg = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
        help_text="Weight (kg) included in base fee at no extra charge"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["min_km"]

    def __str__(self):
        upper = str(self.max_km) + " km" if self.max_km else "unlimited"
        return self.label + " (" + str(self.min_km) + "-" + upper + ")"
