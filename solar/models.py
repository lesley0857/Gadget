from django.db import models

# Create your models here.
from django.db import models


class Appliance(models.Model):

    name = models.CharField(
        max_length=100
    )

    wattage = models.PositiveIntegerField()

    category = models.CharField(
        max_length=50,
        blank=True
    )

    popular = models.BooleanField(
        default=False
    )

    def __str__(self):
        return self.name