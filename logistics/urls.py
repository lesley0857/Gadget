from django.urls import path
from . import views

urlpatterns = [
    # Standalone logistics calculator tool page
    path(
        "calculate-fee/",
        views.logistics_calculator_page,
        name="logistics_calculator",
    ),
    # AJAX: compute fee from vendor + customer coords
    path(
        "api/calculate-fee/",
        views.calculate_logistics_fee_api,
        name="calculate_logistics_fee_api",
    ),
    # AJAX: autocomplete Nigerian city names → coordinates
    path(
        "api/city-lookup/",
        views.city_lookup_api,
        name="city_lookup_api",
    ),
]
