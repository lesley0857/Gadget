from django.contrib import admin
from .models import *
# Register your models here.
admin.site.register(NegotiationRequest)
admin.site.register(NegotiationItem)
admin.site.register(Cart)