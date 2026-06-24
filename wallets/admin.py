from django.contrib import admin

# Register your models here.
from .models import *

@admin.register(VendorWallet)
class VendorWalletAdmin(admin.ModelAdmin):
    list_display = ["vendor", "balance"]

admin.site.register(Commission)