"""Seed a verified Deye inverter/battery range for the solar calculator.

Prices are editable Nigerian market starting prices (NGN), not manufacturer MSRPs.
Run: python manage.py seed_deye_solar --apply
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from accounts.models import User, Vendor
from catalog.models import Category, ProductListing
from solar.models import BatterySpecification, InverterSpecification

INVERTERS = [
    ("SUN-3K-SG04LP1-EU-SM2", 3000, 6000, 48, 230, "single_phase", 1250000),
    ("SUN-5K-SG04LP1-EU-SM2", 5000, 10000, 48, 230, "single_phase", 1650000),
    ("SUN-6K-SG04LP1-EU-SM2", 6000, 12000, 48, 230, "single_phase", 1900000),
    ("SUN-8K-SG05LP1-EU-SM2", 8000, 16000, 48, 230, "single_phase", 2500000),
    ("SUN-12K-SG04LP3-EU", 12000, 24000, 48, 400, "three_phase", 3900000),
    ("SUN-20K-SG05LP3-EU-SM2", 20000, 40000, 48, 400, "three_phase", 5900000),
    ("SUN-50K-SG01HP3-EU", 50000, 100000, 160, 400, "three_phase", 12500000),
]
BATTERIES = [
    ("SE-G5.1 Pro-B", 51.2, 100, 100, 100, 45, 1450000),
    ("AI-W5.1-B", 51.2, 100, 100, 100, 49, 1650000),
]

class Command(BaseCommand):
    help = "Seed Deye hybrid inverters and LiFePO4 batteries for solar calculations."
    def add_arguments(self, parser): parser.add_argument("--apply", action="store_true")
    def handle(self, *args, **options):
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("Dry run. Use --apply to create/update Deye products.")); return
        user, _ = User.objects.get_or_create(email="catalogue@remarobe.local", defaults={"username": "remarobe-catalogue"})
        vendor, _ = Vendor.objects.get_or_create(user=user, defaults={"store_name": "REMAROBE Solar Catalogue"})
        inverter_category, _ = Category.objects.get_or_create(name="Solar Inverters", defaults={"slug": "solar-inverters"})
        battery_category, _ = Category.objects.get_or_create(name="Solar Batteries", defaults={"slug": "solar-batteries"})
        for model, power, surge, dc, output, phase, price in INVERTERS:
            listing, _ = ProductListing.objects.update_or_create(vendor=vendor, model_number=model, defaults={"name": f"Deye {model} Hybrid Inverter", "manufacturer":"Deye", "brand":"Deye", "supplier_price":Decimal(price), "cached_price":Decimal(price), "stock":10, "weight":25, "description":f"Deye hybrid inverter, {power/1000:g} kW, {phase.replace('_', ' ')}.", "technical_specification":f"{dc}V battery; {output}V AC; 50Hz; hybrid inverter.", "is_active":True})
            listing.categories.set([inverter_category])
            InverterSpecification.objects.update_or_create(product=listing, defaults={"rated_power":power,"surge_power":surge,"dc_voltage":dc,"output_voltage":output,"frequency":50,"phase":phase,"efficiency":Decimal("0.97"),"hybrid":True})
        for model, voltage, ah, charge, discharge, weight, price in BATTERIES:
            listing, _ = ProductListing.objects.update_or_create(vendor=vendor, model_number=model, defaults={"name":f"Deye {model} LiFePO4 Battery", "manufacturer":"Deye", "brand":"Deye", "supplier_price":Decimal(price), "cached_price":Decimal(price), "stock":10, "weight":weight, "description":f"Deye {model} 5.12 kWh LiFePO4 battery.", "technical_specification":f"{voltage}V, {ah}Ah, 5.12kWh, CAN/RS485.", "is_active":True})
            listing.categories.set([battery_category])
            BatterySpecification.objects.update_or_create(product=listing, defaults={"battery_type":"lithium","voltage":voltage,"capacity_ah":ah,"depth_of_discharge":Decimal("0.90"),"efficiency":Decimal("0.95"),"max_charge_current":charge,"max_discharge_current":discharge,"cycles":6000,"warranty_years":10,"hybrid_compatible":True,"weight":weight})
        self.stdout.write(self.style.SUCCESS("Deye residential through commercial inverter and battery range seeded."))