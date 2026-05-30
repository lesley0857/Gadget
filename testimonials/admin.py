from django.contrib import admin
from .models import Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "company",
        "rating",
        "featured"
    )

    search_fields = (
        "name",
        "company"
    )

    list_filter = (
        "featured",
        "rating"
    )