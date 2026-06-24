from django.contrib import admin
from django_summernote.admin import SummernoteModelAdmin
from .models import *


@admin.register(BlogPost)
class BlogPostAdmin(
    SummernoteModelAdmin
):

    summernote_fields = (
        "content",
    )

    prepopulated_fields = {
        "slug": ("title",)
    }

    list_display = (
        "title",
        "category",
        "created_at"
    )


admin.site.register(
    BlogCategory
)