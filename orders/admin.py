from django.contrib import admin
import json
from django.utils.html import format_html

from .models import Order, OrderItem
from wallets.models import Commission
from logistics.models import Shipment


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


# =========================
# SHIPMENT INLINE (FULL INFO)
# =========================
class ShipmentInline(admin.TabularInline):
    model = Shipment
    extra = 0
    readonly_fields = [
        "vendor",
        "provider",
        "pickup_address",
        "delivery_address",
        "weight",
        "shipping_fee",
        "total_shipping",
        "status",

        "stage",
        "origin_hub",
        "destination_hub",
    ]


# =========================
# ORDER ADMIN
# =========================
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "customer",
        "total_amount",
        "get_total_commission",
        "get_platform_profit",
        "status",
        "created_at"
    ]

    inlines = [
        OrderItemInline,
        CommissionInline,
        ShipmentInline
    ]

    readonly_fields = [
    "locked_data_table",
    "total_commission_display",
    "platform_profit_display",
    "shipment_summary",

    "billing_address",
    "shipping_address",
    "shipping_city",
    "phone",
]

    # =========================
    # PERFORMANCE
    # =========================
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related("commissions", "shipments")

    # =========================
    # TOTAL COMMISSION
    # =========================
    def get_total_commission(self, obj):
        total = sum(c.total_commission for c in obj.commissions.all())
        return f"₦{total:.2f}"

    get_total_commission.short_description = "Total Commission"

    # =========================
    # PLATFORM PROFIT
    # =========================
    def get_platform_profit(self, obj):
        total = sum(c.total_commission for c in obj.commissions.all())
        return f"₦{total:.2f}"

    get_platform_profit.short_description = "Platform Profit"

    # =========================
    # DISPLAY INSIDE PAGE
    # =========================
    def total_commission_display(self, obj):
        total = sum(c.total_commission for c in obj.commissions.all())
        return f"₦{total:.2f}"

    total_commission_display.short_description = "Total Commission"

    def platform_profit_display(self, obj):
        total = sum(c.total_commission for c in obj.commissions.all())
        return f"₦{total:.2f}"

    platform_profit_display.short_description = "Platform Profit"

    # =========================
    # SHIPMENT TABLE VIEW
    # =========================
    def shipment_summary(self, obj):

        shipments = obj.shipments.all()

        if not shipments:
            return "No shipments"

        html = """

        <h3>CUSTOMER DETAILS</h3>

        <table border="1" cellpadding="6"
            style="border-collapse: collapse; width:100%;">

            <tr>
                <th>Customer</th>
                <th>Phone</th>
                <th>Billing Address</th>
                <th>Shipping Address</th>
            </tr>

            <tr>
                <td>{customer}</td>
                <td>{phone}</td>
                <td>{billing}</td>
                <td>{shipping}</td>
            </tr>

        </table>

        <br><br>

        <h3>SHIPMENTS</h3>

        <table border="1" cellpadding="6"
            style="border-collapse: collapse; width:100%;">

            <tr>
                <th>Stage</th>
                <th>Vendor</th>
                <th>Provider</th>

                <th>Pickup Address</th>
                <th>Delivery Address</th>

                <th>Origin Hub</th>
                <th>Destination Hub</th>

                <th>Weight</th>
                <th>Shipping Fee</th>

                <th>Status</th>
                <th>Tracking ID</th>
            </tr>

        """.format(
            customer=obj.customer,
            phone=obj.phone,
            billing=obj.billing_address,
            shipping=obj.shipping_address,
        )

        for s in shipments:

            html += f"""

            <tr>

                <td>{s.stage}</td>

                <td>{s.vendor}</td>

                <td>{s.provider}</td>

                <td>{s.pickup_address}</td>

                <td>{s.delivery_address}</td>

                <td>{s.origin_hub}</td>

                <td>{s.destination_hub}</td>

                <td>{s.weight}</td>

                <td>₦{s.shipping_fee}</td>

                <td>{s.status}</td>

                <td>{s.tracking_id}</td>

            </tr>

            """

        html += "</table>"

        return format_html(html)
    shipment_summary.short_description = "Shipment Breakdown"

    # =========================
    # LOCKED SNAPSHOT
    # =========================

    from django.utils.html import format_html

    def locked_data_table(self, obj):

        if not obj.locked_data:
            return "No data"

        data = json.loads(obj.locked_data)

        html = """
        <h3>Checkout Snapshot</h3>

        <table border="1" cellpadding="6">
            <tr><th>Subtotal</th><th>Shipping</th><th>VAT</th><th>Total</th></tr>
            <tr>
                <td>₦{subtotal}</td>
                <td>₦{shipping}</td>
                <td>₦{vat}</td>
                <td>₦{total}</td>
            </tr>
        </table>
        """.format(
            subtotal=data.get("subtotal"),
            shipping=data.get("shipping"),
            vat=data.get("vat"),
            total=data.get("total"),
        )

        for v in data.get("vendors_data", []):
            html += f"""
            <h4>{v['vendor_name']}</h4>
            <table border="1" cellpadding="6">
                <tr>
                    <th>Subtotal</th>
                </tr>
                <tr>
                    <td>₦{v['vendor_subtotal']}</td>
                </tr>
            </table>
            """

        return format_html(html)
    
    locked_data_table.short_description = "Locked Checkout Snapshot"


