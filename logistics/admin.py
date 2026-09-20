from django.contrib import admin
from django.contrib import messages
from orders.models import Order
from .models import Shipment, ShipmentUpdate, LogisticsRate


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):

    list_display = [
        "tracking_id",
        "order",
        "status",
        "courier_name",
        "delivery_agent_name",
        "last_update",
    ]

    list_filter = [
        "status",
        "created_at",
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
        return qs.select_related("order")

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

    list_filter = [
        "status",
        "created_at"
    ]

    search_fields = [
        "tracking_id",
        "order__reference",
        "delivery_agent_name",
        "delivery_agent_phone",
    ]

@admin.register(LogisticsRate)
class LogisticsRateAdmin(admin.ModelAdmin):
    list_display = [
        "label",
        "min_km",
        "max_km",
        "base_fee",
        "rate_per_km",
        "weight_rate_per_kg",
        "free_weight_kg",
        "is_active",
    ]
    list_editable = ["is_active"]
    ordering = ["min_km"]
    list_filter = ["is_active"]


@admin.register(ShipmentUpdate)
class ShipmentUpdateAdmin(admin.ModelAdmin):
    list_display = ["shipment", "status", "location", "created_at"]
    list_filter = ["status"]
    ordering = ["-created_at"]
