from django.db import models

# Create your models here.
from accounts.models import *
from cloudinary.models import CloudinaryField
from django.utils import timezone
from decimal import Decimal

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

    MARKUP_PERCENTAGE = "markup_percentage"
    MARKUP_FIXED = "markup_fixed"
    DISCOUNT_PERCENTAGE = "discount_percentage"
    DISCOUNT_FIXED = "discount_fixed"

    RULE_TYPES = [
        (MARKUP_PERCENTAGE, "Markup Percentage"),
        (MARKUP_FIXED, "Markup Fixed"),
        (DISCOUNT_PERCENTAGE, "Discount Percentage"),
        (DISCOUNT_FIXED, "Discount Fixed"),
    ]

    name = models.CharField(max_length=150)

    rule_type = models.CharField(
        max_length=30,
        choices=RULE_TYPES
    )

    value = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    category = models.ForeignKey(
        Category,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    vendor = models.ForeignKey(
        "accounts.Vendor",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pricing_rules"
    )

    product = models.ForeignKey(
        "ProductListing",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pricing_rules"
    )

    priority = models.PositiveIntegerField(
        default=100
    )

    is_default = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    starts_at = models.DateTimeField(
        null=True,
        blank=True
    )

    ends_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["priority"]

    def is_valid(self):
        now = timezone.now()

        if not self.is_active:
            return False

        if self.starts_at and now < self.starts_at:
            return False

        if self.ends_at and now > self.ends_at:
            return False

        return True

    def __str__(self):
        return self.name



class ProductListing(models.Model):
    name = models.CharField(max_length=255)
   

    vendor = models.ForeignKey(
        "accounts.Vendor",
        on_delete=models.CASCADE
    )

    categories = models.ManyToManyField(
        Category,
        related_name="product_listings"
    )

    manufacturer = models.CharField(
        max_length=200,
        blank=True
    )

    brand = models.CharField(
        max_length=200,
        blank=True
    )

    model_number = models.CharField(
        max_length=200,
        blank=True
    )

    country_of_origin = models.CharField(
        max_length=100,
        blank=True
    )

    base_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    minimum_order_quantity = models.PositiveIntegerField(
        default=1
    )

    weight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    description = models.TextField()

    technical_specification = models.TextField(
        blank=True
    )

    warranty_period_months = models.PositiveIntegerField(
        default=0
    )

    lead_time_days = models.PositiveIntegerField(
        default=0
    )

    datasheet = models.FileField(
        upload_to="datasheets/",
        blank=True,
        null=True
    )

    is_negotiable = models.BooleanField(
        default=False
    )

    units_sold = models.PositiveIntegerField(
    default=0
    )

    is_featured = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )
    def get_applicable_rule(self):

        categories = self.categories.all()

        rule = PricingRule.objects.filter(
            product=self,
            is_active=True
        ).order_by("priority").first()

        if rule:
            return rule

        rule = PricingRule.objects.filter(
            vendor=self.vendor,
            category__in=categories,
            is_active=True
        ).order_by("priority").first()

        if rule:
            return rule

        rule = PricingRule.objects.filter(
            vendor=self.vendor,
            category__isnull=True,
            is_active=True
        ).order_by("priority").first()

        if rule:
            return rule

        rule = PricingRule.objects.filter(
            vendor__isnull=True,
            category__in=categories,
            is_active=True
        ).order_by("priority").first()

        if rule:
            return rule

        return PricingRule.objects.filter(
            is_default=True,
            is_active=True
        ).order_by("priority").first()
    
    def final_price(self):

        price = self.base_price

        rule = self.get_applicable_rule()

        if not rule:
            return price

        value = Decimal(rule.value)

        if rule.rule_type == PricingRule.MARKUP_PERCENTAGE:
            price += price * value / 100

        elif rule.rule_type == PricingRule.MARKUP_FIXED:
            price += value

        elif rule.rule_type == PricingRule.DISCOUNT_PERCENTAGE:
            price -= price * value / 100

        elif rule.rule_type == PricingRule.DISCOUNT_FIXED:
            price -= value

        return max(price, Decimal("0.00"))

    final_price.short_description = "Final Price"

class ProductMedia(models.Model):

    IMAGE = "image"
    VIDEO = "video"

    MEDIA_TYPES = [
        (IMAGE, "Image"),
        (VIDEO, "Video"),
    ]

    product_listing = models.ForeignKey(
        ProductListing,
        on_delete=models.CASCADE,
        related_name="media"
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPES
    )

    file = models.FileField(
        upload_to="product_media/"
    )

    is_primary = models.BooleanField(
        default=False
    )

    sort_order = models.PositiveIntegerField(
        default=0
    )

class ProductSpecification(models.Model):

    product = models.ForeignKey(
        ProductListing,
        on_delete=models.CASCADE,
        related_name="specifications"
    )

    name = models.CharField(
        max_length=150
    )

    value = models.CharField(
        max_length=255
    )

    def __str__(self):
        return f"{self.name}: {self.value}"
    
