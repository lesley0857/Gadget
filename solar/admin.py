from django.contrib import admin
from .models import Appliance


@admin.register(Appliance)
class ApplianceAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "wattage",
        "category",
        "popular"
    )

    search_fields = (
        "name",
    )