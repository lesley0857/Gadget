import uuid
from django.db import models

# Create your models here.
from django.conf import settings
from catalog.models import ProductListing
from decimal import Decimal


User = settings.AUTH_USER_MODEL

class Cart(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("locked", "Locked"),
        ("converted", "Converted"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=20, default="active")
    locked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def lock(self):
        from django.utils import timezone
        self.status = "locked"
        self.locked_at = timezone.now()
        self.save()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_listing = models.ForeignKey(ProductListing, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        price = Decimal(str(
            self.product_listing.final_price()
            )
        )
        return price * self.quantity
    

class NegotiationRequest(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("quoted", "Quoted"),
        ("accepted", "Accepted"),
        ("paid", "Paid"),
        ("expired", "Expired"),
    )
    
    NEGOTIATION_TYPE = (
        ("cart", "Cart Negotiation"),
        ("shipping", "Shipping Negotiation"),
    )
    code = models.CharField(
        max_length=20,
        unique=True
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    customer_name = models.CharField(
        max_length=200,
        blank=True
    )

    customer_email = models.EmailField(
        blank=True
    )

    customer_phone = models.CharField(
        max_length=30,
        blank=True
    )

    shipping_address = models.TextField(
        blank=True
    )

    shipping_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    admin_notes = models.TextField(
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )
    cart_signature = models.CharField(max_length=255,blank=True)

    negotiation_type = models.CharField(max_length=20,choices=NEGOTIATION_TYPE,default="cart")
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    payment_token = models.UUIDField(default=uuid.uuid4,unique=True,editable=False)

    payment_link_expires_at = models.DateTimeField(
        null=True,
        blank=True
    )
    def save(self,*args,**kwargs):

        if not self.code:

            self.code = f"NEG-{uuid.uuid4().hex[:8].upper()}"

        super().save(*args,**kwargs)

    def __str__(self):

        return self.code

class NegotiationItem(models.Model):

    negotiation = models.ForeignKey(
        NegotiationRequest,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product_listing = models.ForeignKey(
        ProductListing,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField()

    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    negotiated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    def get_price(self):
        return (
            self.negotiated_price
            if self.negotiated_price is not None
            else self.original_price
        )
    
    def get_total(self):
        price = self.get_price() or Decimal("0.00")
        qty = self.quantity or 0

        return price * qty
    



