from django.contrib import admin, messages
import json
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .models import Order, OrderItem
from wallets.models import Commission, VendorWallet, WalletTransaction
from logistics.models import Shipment
from decimal import Decimal
from django.db import transaction

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "order",
        "product_listing",
        "vendor",
        "quantity",
        "price",
        "total",
        "escrow_amount",
        "commission",
        "status",
        "released",
        "received",
    ]
    list_filter = ["status", "released", "received", "vendor"]
    search_fields = ["order__order_number", "order__reference", "vendor__store_name", "product_listing__name"]
    actions = ["release_escrow_to_vendor", "mark_as_shipped", "mark_as_delivered"]

    @admin.action(description="Release Escrow to Vendor Wallet for selected items")
    def release_escrow_to_vendor(self, request, queryset):
        count = 0
        total_released = Decimal("0.00")
        with transaction.atomic():
            for item in queryset:
                if not item.released and item.escrow_amount > 0:
                    wallet, _ = VendorWallet.objects.get_or_create(vendor=item.vendor)
                    if wallet.escrow_balance >= item.escrow_amount:
                        wallet.escrow_balance -= item.escrow_amount
                    else:
                        wallet.escrow_balance = Decimal("0.00")
                    wallet.balance += item.escrow_amount
                    wallet.save(update_fields=["escrow_balance", "balance"])

                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=item.escrow_amount,
                        type="credit",
                        reference=item.order.reference,
                        description=f"Escrow released by Admin for Order #{item.order.order_number or item.order.id} ({item.product_listing.name})"
                    )
                    item.released = True
                    item.save(update_fields=["released"])
                    count += 1
                    total_released += item.escrow_amount
        self.message_user(
            request,
            f"Successfully released ₦{total_released:,.2f} escrow to vendor wallet for {count} item(s).",
            messages.SUCCESS
        )

    @admin.action(description="Mark selected items as Shipped")
    def mark_as_shipped(self, request, queryset):
        updated = queryset.update(status="shipped")
        self.message_user(request, f"Marked {updated} item(s) as Shipped.", messages.SUCCESS)

    @admin.action(description="Mark selected items as Delivered")
    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status="delivered", received=True, delivered_at=timezone.now())
        self.message_user(request, f"Marked {updated} item(s) as Delivered.", messages.SUCCESS)

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
        "amount_before_gateway_fee",
        "gateway_fee",
        "total_amount",
        "amount_paid",
        "negotiation_badge",
        "status",
        "created_at",
    ]
    search_fields = [
        "order_number", "reference", "email", "phone", "first_name", "last_name",
        "customer__email", "customer__username", "shipping_city", "tracking_number",
        "courier_name", "items__product_listing__name", "items__vendor__store_name",
    ]
    list_filter = ["status", "requires_shipping_negotiation", "created_at", "paid_at"]
    date_hierarchy = "created_at"
    list_select_related = ["customer"]
    list_per_page = 50
    ordering = ["-created_at"]

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
        "amount_before_gateway_fee",
        "gateway_fee",
        "amount_paid",
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

    def get_urls(self):
        return [path("analytics/", self.admin_site.admin_view(self.analytics_view), name="orders_order_analytics")] + super().get_urls()

    def analytics_view(self, request):
        paid = Order.objects.filter(status__in=["paid", "shipped", "out_for_delivery", "delivered"])
        recent = paid.filter(created_at__gte=timezone.now() - timedelta(days=30))
        return render(request, "admin/order_analytics.html", {**self.admin_site.each_context(request), "title": "Order analytics", "order_count": Order.objects.count(), "paid_count": paid.count(), "sales": paid.aggregate(value=Sum("total_amount"))["value"] or 0, "sales_30": recent.aggregate(value=Sum("total_amount"))["value"] or 0, "by_status": Order.objects.values("status").annotate(total=Count("id"), sales=Sum("total_amount")).order_by("status")})

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
                <td>{s.status}</td>
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
        <table border="1" cellpadding="6" style="border-collapse:collapse; width:100%;">
            <tr>
                <th>Subtotal</th>
                <th>Shipping</th>
                <th>Commercial Value (Before Gateway Fee)</th>
                <th>Gateway Fee Recovered</th>
                <th>Gross Total Charged</th>
                <th>Amount Paid</th>
            </tr>
            <tr>
                <td>₦{:,.2f}</td>
                <td>₦{:,.2f}</td>
                <td>₦{:,.2f}</td>
                <td>₦{:,.2f}</td>
                <td>₦{:,.2f}</td>
                <td>₦{:,.2f}</td>
            </tr>
        </table>
        """,
        float(data.get("subtotal") or obj.subtotal or 0),
        float(data.get("shipping") or obj.shipping_amount or obj.shipping_fee or 0),
        float(data.get("amount_before_gateway_fee") or data.get("net_total") or obj.amount_before_gateway_fee or 0),
        float(data.get("gateway_fee") or obj.gateway_fee or 0),
        float(data.get("total") or obj.total_amount or 0),
        float(obj.amount_paid or 0),
        )

    locked_data_table.short_description = "Checkout Summary"



