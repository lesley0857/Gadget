from django.db import models
from django.utils.text import slugify


class BlogCategory(models.Model):

    name = models.CharField(max_length=200)

    slug = models.SlugField(unique=True)
    def __str__(self):
        return self.name


class BlogPost(models.Model):

    title = models.CharField(max_length=300)

    slug = models.SlugField(unique=True)

    excerpt = models.TextField()

    content = models.TextField()

    featured_image = models.ImageField(
        upload_to="blog"
    )

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True
    )

    author = models.CharField(
        max_length=100,
        default="Remarobe Engineering"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    is_published = models.BooleanField(
        default=True
    )

    meta_title = models.CharField(
        max_length=160,
        blank=True
    )

    meta_description = models.TextField(
        blank=True
    )

    keywords = models.TextField(
        blank=True
    )

    linkedin_url = models.URLField(
        blank=True
    )

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title