from django.db import models


class Testimonial(models.Model):

    name = models.CharField(
        max_length=255
    )

    company = models.CharField(
        max_length=255,
        blank=True
    )

    position = models.CharField(
        max_length=255,
        blank=True
    )

    photo = models.ImageField(
        upload_to="testimonials/",
        blank=True,
        null=True
    )

    message = models.TextField()

    rating = models.PositiveSmallIntegerField(
        default=5
    )

    featured = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name