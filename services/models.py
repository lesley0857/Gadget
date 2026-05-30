from django.db import models
from cloudinary.models import CloudinaryField

from django.db import models
from django.utils.text import slugify


# =========================================
# SERVICE
# =========================================

class Service(models.Model):

    title = models.CharField(max_length=255)

    slug = models.SlugField(
        unique=True,
        blank=True
    )

    short_description = models.TextField()

    full_description = models.TextField()

    hero_image = models.ImageField(
        upload_to="services/heroes/",
        blank=True,
        null=True
    )

    icon = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):

        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# =========================================
# SERVICE MEDIA
# =========================================

class ServiceMedia(models.Model):

    IMAGE = "image"
    VIDEO = "video"

    MEDIA_TYPES = [
        (IMAGE, "Image"),
        (VIDEO, "Video"),
    ]

    service = models.ForeignKey(
        Service,
        related_name="media",
        on_delete=models.CASCADE
    )

    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPES
    )

    file = models.FileField(
        upload_to="services/media/"
    )

    title = models.CharField(
        max_length=255,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):

        return f"{self.service.title} - {self.media_type}"
    

class ServiceRFQ(models.Model):

    service = models.ForeignKey(
        'Service',
        on_delete=models.CASCADE,
        related_name="rfqs"
    )

    name = models.CharField(max_length=255)

    email = models.EmailField()

    phone = models.CharField(max_length=50)

    company = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    message = models.TextField()

    document = models.FileField(
        upload_to="rfq_documents/",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_contacted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.service.title}"