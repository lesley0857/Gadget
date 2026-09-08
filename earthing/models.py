from django.db import models
from django.conf import settings
class FieldEarthingDesign(models.Model):
 user=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL)
 project_name=models.CharField(max_length=255); installation_type=models.CharField(max_length=50); inputs=models.JSONField(); result=models.JSONField(); created_at=models.DateTimeField(auto_now_add=True)
