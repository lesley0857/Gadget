from django.contrib import admin
import json
from django.utils.html import format_html

from .models import Order, OrderItem
from wallets.models import Commission
from logistics.models import Shipment

admin.site.register(OrderItem)

# =========================
# ORDER ITEMS INLINE
# =========================
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        "product_listing",
        "vendor",
        "quantity",
        "price",
        "total",
        "commission",
        "escrow_amount",
        "status"
    ]


# =========================
# COMMISSION INLINE
# =========================
class CommissionInline(admin.TabularInline):
    model = Commission
    extra = 0
    readonly_fields = [
        "vendor",
        "order_item",
        "product_commission",
        "shipping_commission",
        "total_commission",
    ]

class ShipmentInline(admin.TabularInline):
    model = Shipment
    extra = 0

    readonly_fields = [
        "tracking_id",
        "order",
        "created_at",
        "last_update",
    ]

    fields = [
        "tracking_id",
        "status",
        "current_location",
        "delivery_agent_name",
        "delivery_agent_phone",
        "last_update",
    ]
# =========================
# ORDER ADMIN
# =========================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "customer",
        "order_number",
        "total_amount",
        "negotiation_badge",
        "status",
        "created_at",
    ]
    def negotiation_badge(self,obj):

        if obj.negotiation:
            return "YES"

        return "-"

    negotiation_badge.short_description = "Negotiated"
    inlines = [
        OrderItemInline,
        ShipmentInline,
        CommissionInline,
    ]

    readonly_fields = [
        "locked_data_table",
        "shipment_summary",
        "billing_address",
        "shipping_address",
        "phone",
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            "commissions",
            "shipments"
        )

    # =========================
    # SIMPLE COMMISSION TOTAL
    # =========================
    def _total_commission(self, obj):
        return sum(c.total_commission for c in obj.commissions.all())

    # =========================
    # SHIPMENT SUMMARY (SIMPLIFIED)
    # =========================
    def shipment_summary(self, obj):

        shipments = obj.shipments.all()

        if not shipments:
            return "No shipments"

        html = """
        <h3>Shipments</h3>

        <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
            <tr>
                <th>Stage</th>
                <th>Vendor</th>
                <th>Provider</th>
                <th>From</th>
                <th>To</th>
                <th>Status</th>
                <th>Tracking</th>
            </tr>
        """

        for s in shipments:
            html += f"""
            <tr>
                <td>{s.stage}</td>
                <td>{s.vendor or '-'}</td>
                <td>{s.provider}</td>
                <td>{s.pickup_address}</td>
                <td>{s.delivery_address}</td>
                <td>{s.status}</td>
                <td>{s.tracking_id}</td>
            </tr>
            """

        html += "</table>"

        return format_html(html)

    shipment_summary.short_description = "Shipments"

    # =========================
    # LOCKED SNAPSHOT (SIMPLIFIED)
    # =========================
    def locked_data_table(self, obj):

        if not obj.locked_data:
            return "No data"

        data = obj.locked_data or {}

        return format_html("""
        <table border="1" cellpadding="6" style="border-collapse:collapse;">
            <tr>
                <th>Subtotal</th>
                <th>Shipping</th>
                <th>VAT</th>
                <th>Total</th>
            </tr>
            <tr>
                <td>₦{}</td>
                <td>₦{}</td>
                <td>₦{}</td>
                <td>₦{}</td>
            </tr>
        </table>
        """,
        data.get("subtotal", 0),
        data.get("shipping", 0),
        data.get("vat", 0),
        data.get("total", 0)
        )

    locked_data_table.short_description = "Checkout Summary"



