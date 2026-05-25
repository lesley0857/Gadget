from django.contrib import admin
from orders.models import Order

# Register your models here.
from .models import *

admin.site.register(Shipment)
admin.site.register(ShippingOption)
admin.site.register(ShippingProvider)
admin.site.register(Hub)

@admin.register(ShippingNegotiation)
class ShippingNegotiationAdmin(admin.ModelAdmin):

    list_display = [
        "code",
        "customer",
        "subtotal",
        "shipping_fee",
        "final_total",
        "status",
        "created_at"
    ]

    readonly_fields = [
        "code",
        "customer",
        "subtotal",
        "vat",
        "locked_data",
        "final_total",
    ]

    list_filter = [
        "status",
        "created_at"
    ]

    search_fields = [
        "code",
        "customer__username",
        "customer__email"
    ]