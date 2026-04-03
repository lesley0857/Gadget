from django.db import models
from catalog.models import *
from accounts.models import Vendor

# class PricingRule(models.Model):
#     PERCENTAGE = "percentage"
#     FIXED = "fixed"

#     pricing_type = models.CharField(
#         max_length=20,
#         choices=[(PERCENTAGE, "Percentage"), (FIXED, "Fixed")]
#     )
#     value = models.DecimalField(max_digits=10, decimal_places=2)

#     category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE)
#     vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.CASCADE)
#     is_default = models.BooleanField(default=False)
#     priority = models.PositiveIntegerField(default=1)

#     def __str__(self):
#         return f"{self.pricing_type} - {self.value}"