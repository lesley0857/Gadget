from django.db import models
from orders.models import OrderItem
from accounts.models import User

class Dispute(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    raised_by = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, default="open")
    resolved = models.BooleanField(default=False)

class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE)
    file = models.ImageField(upload_to="disputes/")
