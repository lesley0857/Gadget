from django.db import models
from orders.models import Order

class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20)
    raw_response = models.JSONField()

class ShippingRule(models.Model):
    name = models.CharField(max_length=100)

    same_state_fee = models.DecimalField(max_digits=10, decimal_places=2)
    interstate_fee = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
class VAT(models.Model):
    name = models.CharField(max_length=50)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)  # e.g 7.5
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"
    

