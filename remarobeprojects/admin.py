from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "client",
        "status",
        "featured",
        "completion_date"
    )

    prepopulated_fields = {
        "slug": ("title",)
    }

    search_fields = (
        "title",
        "client",
        "location"
    )

    list_filter = (
        "status",
        "featured"
    )