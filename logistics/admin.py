from django.contrib import admin
from orders.models import Order

# Register your models here.
from .models import *

admin.site.register(Shipment)
admin.site.register(ShippingOption)
admin.site.register(ShippingProvider)
admin.site.register(Hub)