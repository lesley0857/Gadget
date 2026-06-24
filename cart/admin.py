from django.contrib import admin
from django.db.models import Sum
from django.urls import reverse
from django.utils.html import format_html

from .models import (
Cart,
NegotiationRequest,
NegotiationItem
)

from logistics.models import Shipment

class NegotiationItemInline(admin.TabularInline):
    model = NegotiationItem

    extra = 0

    readonly_fields = (
        "product_listing",
        "quantity",
        "original_price",
        "line_total",
    )

    fields = (
        "product_listing",
        "quantity",
        "original_price",
        "negotiated_price",
        "line_total",
    )

    def line_total(self, obj):
        try:
            return obj.get_total()
        except Exception:
            return "N/A"

    line_total.short_description = "Line Total"


@admin.register(NegotiationRequest)
class NegotiationRequestAdmin(admin.ModelAdmin):

    inlines = [NegotiationItemInline]

    list_display = (

        "code",

        "customer",

        "negotiation_type",

        "status",

        "total_amount",

        "shipping_fee",

        "created_at",

        "order_link",

        "shipment_link",
    )

    list_filter = (

        "status",

        "negotiation_type",

        "created_at",
    )

    search_fields = (

        "code",

        "customer_name",

        "customer_email",

        "customer_phone",

        "user__username",

        "user__email",
    )

    readonly_fields = (

        "code",

        "created_at",

        "payment_token",

        "payment_reference",

        "order_link",

        "shipment_link",
    )

    fieldsets = (

        (
            "Negotiation Details",
            {
                "fields": (
                    "code",
                    "status",
                    "negotiation_type",
                    "created_at",
                )
            }
        ),

        (
            "Customer",
            {
                "fields": (
                    "user",
                    "customer_name",
                    "customer_email",
                    "customer_phone",
                    "shipping_address",
                )
            }
        ),

        (
            "Quotation",
            {
                "fields": (
                    "shipping_fee",
                    "admin_notes",
                    "payment_token",
                    "payment_reference",
                )
            }
        ),

        (
            "Order",
            {
                "fields": (
                    "order_link",
                    "shipment_link",
                )
            }
        ),
    )

    actions = [

        "mark_quoted",

        "mark_expired",
    ]

    def customer(self,obj):

        return (
            obj.customer_name
            or
            obj.user
        )

    customer.short_description = "Customer"

    def total_amount(self,obj):

        total = 0

        for item in obj.items.all():

            total += item.get_total()

        total += obj.shipping_fee

        return f"₦{total:,.2f}"

    total_amount.short_description = "Quote Total"

    def order_link(self,obj):

        if not obj.order:

            return "-"

        url = reverse(
            "admin:orders_order_change",
            args=[obj.order.id]
        )

        return format_html(
            '<a href="{}">View Order</a>',
            url
        )

    order_link.short_description = "Order"

    def shipment_link(self,obj):

        if not obj.order:

            return "-"

        shipment = Shipment.objects.filter(
            order=obj.order
        ).first()

        if not shipment:

            return "-"

        url = reverse(
            "admin:logistics_shipment_change",
            args=[shipment.id]
        )

        return format_html(
            '<a href="{}">Track Shipment</a>',
            url
        )

    shipment_link.short_description = "Shipment"

    def mark_quoted(self,request,queryset):

        updated = queryset.update(
            status="quoted"
        )

        self.message_user(
            request,
            f"{updated} negotiations marked as quoted."
        )

    mark_quoted.short_description = (
        "Mark selected as Quoted"
    )

    def mark_expired(self,request,queryset):

        updated = queryset.update(
            status="expired"
        )

        self.message_user(
            request,
            f"{updated} negotiations expired."
        )

    mark_expired.short_description = (
        "Mark selected as Expired"
    )


@admin.register(NegotiationItem)
class NegotiationItemAdmin(admin.ModelAdmin):
    list_display = (

        "negotiation",

        "product_listing",

        "quantity",

        "original_price",

        "negotiated_price",
    )

    search_fields = (

        "negotiation__code",

        "product_listing__name",
    )

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "created_at",
        "status",
    )

    search_fields = (
        "user__username",
        "user__email",
    )
