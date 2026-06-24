from django.contrib import admin
from .models import Category, ProductListing, ProductMedia, PricingRule
from accounts.models import Vendor


# ✅ CATEGORY
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ["name"]

# ✅ PRICING RULE
@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ["rule_type",
        "value",
        "category",
        "vendor",
        "priority",
        "is_active",
        ]
    
    def display_final_price(self, obj):
        return obj.final_price()

    display_final_price.short_description = "Final Price"


# ✅ MEDIA INLINE
class ProductMediaInline(admin.TabularInline):
    model = ProductMedia
    extra = 1


# ✅ PRODUCT LISTING
@admin.register(ProductListing)
class ProductListingAdmin(admin.ModelAdmin):
    list_display = ["name",
        "vendor",
        "supplier_price",
        "selling_price",
        "profit",
        "display_final_price",
        "stock",
        "is_active",]
    
    def display_final_price(self, obj):
        return obj.final_price

    display_final_price.short_description = "Final Price"
    
    @admin.display(description="Selling Price")
    def selling_price(self,obj):
        return f"₦{obj.final_price():,.2f}"
    
    @admin.display(description="Profit")
    def profit(self,obj):
        return f"₦{obj.profit_amount:,.2f}"

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
    autocomplete_fields = ["vendor"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "vendor":

            if request.user.is_superuser:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

            kwargs["queryset"] = Vendor.objects.filter(user=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


    inlines = [ProductMediaInline]

