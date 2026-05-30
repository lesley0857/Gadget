from django.db import models


class Project(models.Model):

    STATUS_CHOICES = (
        ("completed", "Completed"),
        ("ongoing", "Ongoing"),
    )

    title = models.CharField(max_length=255)

    slug = models.SlugField(unique=True)

    client = models.CharField(
        max_length=255,
        blank=True
    )

    location = models.CharField(
        max_length=255,
        blank=True
    )

    short_description = models.TextField()

    full_description = models.TextField()

    featured_image = models.ImageField(
        upload_to="projects/"
    )

    completion_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="completed"
    )

    featured = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title