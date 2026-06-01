from django.contrib import admin
from orders.models import Order

# Register your models here.
from .models import *
admin.site.register(ShippingOption)
admin.site.register(ShippingProvider)
admin.site.register(Hub)
from django.contrib import admin
from django.contrib import messages
from .models import Shipment


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):

    list_display = [
        "tracking_id",
        "order",
        "status",
        "vendor",
        "delivery_agent_name",
        "last_update",
    ]

    list_filter = [
        "status",
        "created_at",
        "vendor",
    ]

    search_fields = [
        "tracking_id",
        "order__reference",
        "delivery_agent_name",
        "delivery_agent_phone",
    ]

    ordering = ["-created_at"]

    actions = [
        "mark_picked",
        "mark_in_transit",
        "mark_out_for_delivery",
        "mark_delivered",
    ]

    # =========================
    # OPTIMIZATION
    # =========================
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("order", "vendor")

    # =========================
    # ACTIONS
    # =========================

    def mark_picked(self, request, queryset):
        updated = queryset.update(status="picked")
        self.message_user(
            request,
            f"{updated} shipment(s) marked as PICKED",
            messages.SUCCESS
        )

    mark_picked.short_description = "Mark selected as Picked"

    def mark_in_transit(self, request, queryset):
        updated = queryset.update(status="in_transit")
        self.message_user(
            request,
            f"{updated} shipment(s) marked as IN TRANSIT",
            messages.SUCCESS
        )

    mark_in_transit.short_description = "Mark selected as In Transit"

    def mark_out_for_delivery(self, request, queryset):
        updated = queryset.update(status="out_for_delivery")
        self.message_user(
            request,
            f"{updated} shipment(s) marked as OUT FOR DELIVERY",
            messages.SUCCESS
        )

    mark_out_for_delivery.short_description = "Mark selected as Out for Delivery"

    def mark_delivered(self, request, queryset):
        updated = queryset.update(status="delivered")
        self.message_user(
            request,
            f"{updated} shipment(s) marked as DELIVERED",
            messages.SUCCESS
        )

    mark_delivered.short_description = "Mark selected as Delivered"



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