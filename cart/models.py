from django.db import models

# Create your models here.
from django.conf import settings
from catalog.models import ProductListing

User = settings.AUTH_USER_MODEL


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_listing = models.ForeignKey(ProductListing, on_delete=models.CASCADE)

    quantity = models.PositiveIntegerField(default=1)

    def get_total_price(self):
        return self.product_listing.final_price * self.quantity