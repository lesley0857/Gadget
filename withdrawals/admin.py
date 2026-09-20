from django.contrib import admin, messages
from django.db import transaction
from .models import WithdrawalRequest
from wallets.models import VendorWallet, WalletTransaction


@admin.register(WithdrawalRequest)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ["vendor", "amount", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["vendor__store_name", "vendor__user__email"]
    actions = ["mark_as_paid_manually", "approve_withdrawals", "reject_and_refund"]

    @admin.action(description="Mark as Paid Manually (Admin sent funds directly)")
    def mark_as_paid_manually(self, request, queryset):
        count = 0
        for withdrawal in queryset.filter(status__in=["pending", "approved"]):
            withdrawal.status = "paid"
            withdrawal.save(update_fields=["status"])
            count += 1
        self.message_user(request, f"Marked {count} withdrawal request(s) as Paid.", messages.SUCCESS)

    @admin.action(description="Approve selected withdrawals")
    def approve_withdrawals(self, request, queryset):
        updated = queryset.filter(status="pending").update(status="approved")
        self.message_user(request, f"Approved {updated} withdrawal request(s).", messages.SUCCESS)

    @admin.action(description="Reject selected withdrawals and refund wallet balance")
    def reject_and_refund(self, request, queryset):
        count = 0
        with transaction.atomic():
            for withdrawal in queryset.filter(status__in=["pending", "approved"]):
                withdrawal.status = "rejected"
                withdrawal.save(update_fields=["status"])
                wallet, _ = VendorWallet.objects.get_or_create(vendor=withdrawal.vendor)
                wallet.balance += withdrawal.amount
                wallet.save(update_fields=["balance"])
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=withdrawal.amount,
                    type="credit",
                    reference=f"WITHDRAWAL-REFUND-{withdrawal.id}",
                    description=f"Refund of rejected withdrawal request #{withdrawal.id}"
                )
                count += 1
        self.message_user(request, f"Rejected and refunded {count} withdrawal request(s).", messages.SUCCESS)