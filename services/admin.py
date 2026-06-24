from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin

from .models import *


# =========================================
# INLINE MEDIA
# =========================================

class ServiceMediaInline(admin.TabularInline):

    model = ServiceMedia

    extra = 1


# =========================================
# SERVICE ADMIN
# =========================================

@admin.register(Service)
class ServiceAdmin(SummernoteModelAdmin):

    summernote_fields = (
        "short_description",
        "full_description",
    )

    inlines = [
        ServiceMediaInline
    ]

    list_display = (
        "title",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "title",
    )

    prepopulated_fields = {
        "slug": ("title",)
    }




@admin.register(ServiceRFQ)
class ServiceRFQAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "service",
        "email",
        "phone",
        "created_at",
        "is_contacted"
    )

    list_filter = (
        "is_contacted",
        "created_at"
    )

    search_fields = (
        "name",
        "email",
        "phone",
        "company"
    )