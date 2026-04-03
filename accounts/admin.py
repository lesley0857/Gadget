from django.contrib import admin
from .models import *
# Register your models here.
from django.contrib.admin import AdminSite

class MyAdminSite(AdminSite):
    login_template = "admin/login.html"

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    search_fields = ["store_name", "user__email"]

admin.site.register(User)