from django.contrib import admin

# Register your models here.
from .models import *
from django.contrib import admin
from .models import OrderItem


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = ["id", "customer", "total_amount", "status", "created_at"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        # 🔥 Only orders containing this vendor
        return qs.filter(items__vendor__user=request.user).distinct()


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):

    list_display = ["get_product", "vendor", "quantity", "released"]

    def get_product(self, obj):
        return obj.product_listing.product.name
    get_product.short_description = "Product"

    # 🔥 FILTER LIST VIEW
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs

        return qs.filter(vendor__user=request.user)

    # 🔥 FILTER DROPDOWNS
    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if not request.user.is_superuser:

            if db_field.name == "vendor":
                kwargs["queryset"] = Vendor.objects.filter(user=request.user)

            if db_field.name == "product_listing":
                kwargs["queryset"] = ProductListing.objects.filter(
                    vendor__user=request.user
                )

            if db_field.name == "order":
                kwargs["queryset"] = Order.objects.filter(
                    items__vendor__user=request.user
                ).distinct()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)