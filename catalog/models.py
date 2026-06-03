from django.db import models

# Create your models here.
from accounts.models import *
from cloudinary.models import CloudinaryField

class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    image = models.ImageField(
        upload_to="categories/",
        blank=True,
        null=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    display_order = models.PositiveIntegerField(
        default=0
    )

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def featured_products(self):
        return self.product_listings.filter(
            is_active=True
        ).distinct()[:4]


class PricingRule(models.Model):
    PERCENTAGE = "percentage"
    FIXED = "fixed"

    pricing_type = models.CharField(
        max_length=20,
        choices=[(PERCENTAGE, "Percentage"), (FIXED, "Fixed")]
    )
    value = models.DecimalField(max_digits=10, decimal_places=2)

    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)
    vendor = models.ForeignKey('accounts.Vendor', null=True, blank=True, on_delete=models.CASCADE,related_name='vendor_rule')
    is_default = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.pricing_type} - {self.value}"
    
class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name

    
class ProductListing(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="listings")
    vendor = models.ForeignKey('accounts.Vendor', on_delete=models.CASCADE)
    categories = models.ManyToManyField(Category, related_name="product_listings")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
    description = models.TextField(blank=True)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=1.0)

    def __str__(self):
        return f"{self.product.name}--{self.vendor}"
    
    def get_applicable_rule(self):

        categories = self.categories.all()

        # 1. Vendor + ANY category
        rule = PricingRule.objects.filter(
            vendor=self.vendor,
            category__in=categories
        ).order_by('priority').first()
        if rule:
            return rule

        # 2. Vendor only
        rule = PricingRule.objects.filter(
            vendor=self.vendor,
            category__isnull=True
        ).order_by('priority').first()
        if rule:
            return rule

        # 3. Category only
        rule = PricingRule.objects.filter(
            vendor__isnull=True,
            category__in=categories
        ).order_by('priority').first()
        if rule:
            return rule

        # 4. Default rule
        return PricingRule.objects.filter(
            is_default=True
        ).order_by('priority').first()


    def calculate_price(self):
        rule = self.get_applicable_rule()

        if not rule:
            return self.base_price

        if rule.pricing_type == PricingRule.PERCENTAGE:
            return self.base_price + (self.base_price * rule.value / 100)

        elif rule.pricing_type == PricingRule.FIXED:
            return self.base_price + rule.value

        return self.base_price


class ProductMedia(models.Model):

    IMAGE = "image"
    VIDEO = "video"

    MEDIA_TYPE_CHOICES = [
        (IMAGE, "Image"),
        (VIDEO, "Video"),
    ]

    product_listing = models.ForeignKey(
        "ProductListing",
        on_delete=models.CASCADE,
        related_name="media"
    )

    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES
    )

    file = models.FileField(
    upload_to="product_media/"
    )

    is_primary = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_listing} - {self.media_type}"

    def save(self, *args, **kwargs):

        if self.is_primary:
            ProductMedia.objects.filter(
                product_listing=self.product_listing,
                is_primary=True
            ).update(is_primary=False)

        super().save(*args, **kwargs)

    
# class ProductMedia(models.Model):
#     IMAGE = "image"
#     VIDEO = "video"

#     MEDIA_TYPE_CHOICES = [
#         (IMAGE, "Image"),
#         (VIDEO, "Video"),
#     ]

#     product_listing = models.ForeignKey(
#         ProductListing,
#         on_delete=models.CASCADE,
#         related_name="media"
#     )

#     media_type = models.CharField(
#         max_length=10,
#         choices=MEDIA_TYPE_CHOICES
#     )

#     file = models.FileField(upload_to="products/")

#     is_primary = models.BooleanField(default=False)  # main display image
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"{self.product_listing} - {self.media_type}"
    
#     def save(self, *args, **kwargs):
#         if self.is_primary:
#             ProductMedia.objects.filter(
#                 product_listing=self.product_listing,
#                 is_primary=True
#             ).update(is_primary=False)

#         super().save(*args, **kwargs)

    