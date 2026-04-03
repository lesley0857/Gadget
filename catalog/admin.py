from django.contrib import admin
from .models import Category, Product, ProductListing, ProductMedia, PricingRule
from accounts.models import Vendor


# ✅ CATEGORY
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]


# ✅ PRODUCT (REQUIRED FOR AUTOCOMPLETE)
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ["name"]

# ✅ PRICING RULE
@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ["pricing_type", "value", "category", "vendor", "priority"]


# ✅ MEDIA INLINE
class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1


# ✅ PRODUCT LISTING
@admin.register(ProductListing)
class ProductListingAdmin(admin.ModelAdmin):
    list_display = ["product", "vendor", "final_price", "stock"]

    # 🔍 REQUIRED
    search_fields = [
        "product__name",
        "vendor__store__name",
        "vendor__user__email"
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(vendor__user=request.user)
    
    # ⚡ AUTOCOMPLETE
    autocomplete_fields = ["product", "vendor"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "vendor":

            if request.user.is_superuser:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

            kwargs["queryset"] = Vendor.objects.filter(user=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


    inlines = [ProductMediaInline]

