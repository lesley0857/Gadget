from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .prod_reso import ProductListingResource
from .models import Category, ProductListing, ProductMedia, PricingRule
from accounts.models import Vendor
from solar.models import *
from .prod_reso import *

from solar.models import (
    BatterySpecification,
    PanelSpecification,
    InverterSpecification,
    ControllerSpecification,
    CableSpecification,
    FuseSpecification,
    BreakerSpecification,
    SPDSpecification,
    IsolatorSpecification,
    MountingStructureSpecification,
    AccessorySpecification,
)


class BatterySpecInline(admin.StackedInline):
    model = BatterySpecification
    extra = 0
    max_num = 1


class PanelSpecInline(admin.StackedInline):
    model = PanelSpecification
    extra = 0
    max_num = 1


class InverterSpecInline(admin.StackedInline):
    model = InverterSpecification
    extra = 0
    max_num = 1


class ControllerSpecInline(admin.StackedInline):
    model = ControllerSpecification
    extra = 0
    max_num = 1


class CableSpecInline(admin.StackedInline):
    model = CableSpecification
    extra = 0
    max_num = 1


class FuseSpecInline(admin.StackedInline):
    model = FuseSpecification
    extra = 0
    max_num = 1


class BreakerSpecInline(admin.StackedInline):
    model = BreakerSpecification
    extra = 0
    max_num = 1


class SPDSpecInline(admin.StackedInline):
    model = SPDSpecification
    extra = 0
    max_num = 1


class IsolatorSpecInline(admin.StackedInline):
    model = IsolatorSpecification
    extra = 0
    max_num = 1


class MountingStructureSpecInline(admin.StackedInline):
    model = MountingStructureSpecification
    extra = 0
    max_num = 1


class AccessorySpecInline(admin.StackedInline):
    model = AccessorySpecification
    extra = 0
    max_num = 1




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
class ProductListingAdmin(ImportExportModelAdmin):
    resource_class = ProductListingResource
    list_display = ["name",
        "vendor",
        "supplier_price",
        "selling_price",
        "profit",
        "display_final_price",
        "stock",
        "is_active",]
    
    def display_final_price(self, obj):
        return obj.final_price()

    display_final_price.short_description = "Final Price"
    
    @admin.display(description="Selling Price")
    def selling_price(self,obj):
        return f"₦{obj.final_price():,.2f}"
    
    @admin.display(description="Profit")
    def profit(self,obj):
        return f"₦{obj.profit_amount:,.2f}"

    # 🔍 REQUIRED
    search_fields = [
        "name",
        "vendor__store__name",
        "vendor__user__email"
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(vendor__user=request.user)

    def get_export_queryset(self, request):
        """Avoid one specification query per product when exporting CSV."""
        return super().get_export_queryset(request).select_related(
            "battery_spec", "panel_spec", "inverter_spec", "controller_spec",
            "cable_spec", "fuse_spec", "breaker_spec", "spd_spec",
            "isolator_spec", "mounting_structure_spec", "accessory_spec",
        )
    
    # ⚡ AUTOCOMPLETE
    autocomplete_fields = ["vendor"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "vendor":

            if request.user.is_superuser:
                return super().formfield_for_foreignkey(db_field, request, **kwargs)

            kwargs["queryset"] = Vendor.objects.filter(user=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


    inlines = [ProductMediaInline,BatterySpecInline, PanelSpecInline, InverterSpecInline,
       ControllerSpecInline, CableSpecInline, FuseSpecInline,
       BreakerSpecInline, SPDSpecInline, IsolatorSpecInline,
       MountingStructureSpecInline, AccessorySpecInline,]

