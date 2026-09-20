from django.contrib import admin, messages
from django.db import transaction
from decimal import Decimal
from .models import VendorWallet, WalletTransaction, Commission


@admin.register(VendorWallet)
class VendorWalletAdmin(admin.ModelAdmin):
    list_display = ["vendor", "get_store_name", "get_vendor_phone", "escrow_balance", "balance"]
    search_fields = ["vendor__store_name", "vendor__user__email", "vendor__phone"]
    readonly_fields = []
    actions = ["release_all_escrow_to_balance", "payout_balance_manually"]

    def get_store_name(self, obj):
        return obj.vendor.store_name if obj.vendor else "—"
    get_store_name.short_description = "Store Name"

    def get_vendor_phone(self, obj):
        return obj.vendor.phone if obj.vendor else "—"
    get_vendor_phone.short_description = "Phone"

    @admin.action(description="Release all Escrow to Available Balance for selected vendors")
    def release_all_escrow_to_balance(self, request, queryset):
        released_count = 0
        total_amount = Decimal("0.00")
        with transaction.atomic():
            for wallet in queryset:
                if wallet.escrow_balance > Decimal("0.00"):
                    amount = wallet.escrow_balance
                    wallet.balance += amount
                    wallet.escrow_balance = Decimal("0.00")
                    wallet.save(update_fields=["balance", "escrow_balance"])
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=amount,
                        type="credit",
                        reference=f"ADMIN-RELEASE-{wallet.id}",
                        description="Escrow released to available balance by Admin"
                    )
                    released_count += 1
                    total_amount += amount
        self.message_user(
            request,
            f"Successfully released ₦{total_amount:,.2f} from escrow to balance for {released_count} vendor(s).",
            messages.SUCCESS
        )

    @admin.action(description="Send Manual Payout (Clear available balance as paid out)")
    def payout_balance_manually(self, request, queryset):
        paid_count = 0
        total_paid = Decimal("0.00")
        with transaction.atomic():
            for wallet in queryset:
                if wallet.balance > Decimal("0.00"):
                    amount = wallet.balance
                    wallet.balance = Decimal("0.00")
                    wallet.save(update_fields=["balance"])
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=amount,
                        type="debit",
                        reference=f"ADMIN-MANUAL-PAYOUT-{wallet.id}",
                        description=f"Manual payout of ₦{amount:,.2f} sent to vendor {wallet.vendor.store_name} by Admin"
                    )
                    paid_count += 1
                    total_paid += amount
        self.message_user(
            request,
            f"Successfully recorded manual payout of ₦{total_paid:,.2f} to {paid_count} vendor(s).",
            messages.SUCCESS
        )


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "wallet", "type", "amount", "reference", "description", "created_at"]
    list_filter = ["type", "created_at"]
    search_fields = ["wallet__vendor__store_name", "reference", "description"]
    readonly_fields = ["wallet", "type", "amount", "reference", "description", "created_at"]


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "vendor", "order_item", "product_commission", "shipping_commission", "total_commission", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["vendor__store_name", "order__order_number", "order__reference"]
    readonly_fields = ["order", "order_item", "vendor", "product_commission", "shipping_commission", "total_commission", "created_at"]