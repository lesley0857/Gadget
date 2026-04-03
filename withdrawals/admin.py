from django.contrib import admin

# Register your models here.
from .models import *


@admin.register(WithdrawalRequest)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ["vendor", "amount", "status"]
    actions = ["approve_withdrawals"]

    def approve_withdrawals(self, request, queryset):
        for withdrawal in queryset:
            withdrawal.status = "approved"
            withdrawal.save()