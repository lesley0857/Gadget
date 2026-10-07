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
        "created_at",
        "linkedin_post_id",
    )
    readonly_fields = ("linkedin_post_id", "linkedin_publish_error")


admin.site.register(
    BlogCategory
)