from django.db import models

# Create your models here.

from django.db import models


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
        ("pending", "Pending"),
        ("booked", "Booked"),
        ("in_transit", "In Transit"),
        ("delivered", "Delivered"),
    ]

    STAGE_CHOICES = [
        ("vendor_to_hub", "Vendor → Hub"),
        ("hub_to_hub", "Hub → Hub"),
        ("hub_to_customer", "Hub → Customer"),
    ]

    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="shipments")
    vendor = models.ForeignKey("accounts.Vendor", on_delete=models.CASCADE,null=True,
    blank=True)
    provider = models.CharField(max_length=50)  # kwik, gigl, etc
    option_name = models.CharField(max_length=100)  # bike, express, etc
    platform_margin = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_shipping = models.DecimalField(max_digits=10, decimal_places=2)
    job_id = models.CharField(max_length=100, blank=True, null=True)  # from KWIK
    status = models.CharField(max_length=20, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    tracking_id = models.CharField(max_length=100, blank=True)
    pickup_address = models.TextField(null=True, blank=True)
    delivery_address = models.TextField(null=True, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2)

    
    origin_hub = models.ForeignKey(
        Hub,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="origin_shipments"
    )
    stage = models.CharField(max_length=30, choices=STAGE_CHOICES,default="vendor_to_hub")
    destination_hub = models.ForeignKey(
        Hub,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="destination_shipments"
    )


    def __str__(self):
        return f"{self.order.id} - {self.vendor}-{self.provider}"
    



