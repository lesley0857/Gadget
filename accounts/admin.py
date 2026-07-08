from django.contrib import admin
from .models import *
# Register your models here.
from django.contrib.admin import AdminSite

class MyAdminSite(AdminSite):
    login_template = "admin/login.html"

@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    search_fields = ["store_name", "user__email"]

@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    list_display = (
        "email",
        "username",
        "is_vendor",
        "is_staff"
    )

    search_fields = (
        "email",
        "username"
    )

    list_filter = (
        "is_vendor",
        "is_staff"
    )

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "phone",
        "city",
        "state"
    )

    search_fields = (
        "user__email",
        "phone"
    )