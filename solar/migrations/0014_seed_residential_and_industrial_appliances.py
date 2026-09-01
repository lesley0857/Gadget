from decimal import Decimal
from django.db import migrations


RESIDENTIAL = [
    ("LED bulb", 10, "lighting", 1, "Lighting"), ("Ceiling fan", 75, "motor", 2, "Cooling"),
    ("Standing fan", 90, "motor", 2, "Cooling"), ("Television (LED)", 100, "electronics", 1, "Entertainment"),
    ("Decoder", 25, "electronics", 1, "Entertainment"), ("Laptop", 65, "electronics", 1, "Office"),
    ("Desktop computer", 200, "electronics", 1, "Office"), ("Refrigerator", 180, "compressor", 3, "Kitchen"),
    ("Deep freezer", 300, "compressor", 3, "Kitchen"), ("Microwave oven", 1200, "resistive", 1, "Kitchen"),
    ("Electric iron", 1200, "resistive", 1, "Laundry"), ("Washing machine", 500, "motor", 2, "Laundry"),
    ("Water pump (0.5 hp)", 370, "motor", 3, "Water"), ("Air conditioner (1 hp)", 900, "compressor", 4, "Cooling"),
    ("Air conditioner (1.5 hp)", 1500, "compressor", 4, "Cooling"), ("Electric kettle", 2000, "resistive", 1, "Kitchen"),
    ("Blender", 500, "motor", 2, "Kitchen"), ("Phone charger", 15, "electronics", 1, "Office"),
]
INDUSTRIAL = [
    ("LED high-bay light", 150, "lighting", 1, "Lighting"), ("LED floodlight", 200, "lighting", 1, "Lighting"),
    ("Office workstation", 250, "electronics", 1, "Office"), ("Server rack", 800, "electronics", 1, "IT"),
    ("CCTV system (8 cameras)", 160, "electronics", 1, "Security"), ("Industrial refrigerator", 1200, "compressor", 3, "Refrigeration"),
    ("Walk-in cold-room condensing unit", 3500, "compressor", 5, "Refrigeration"), ("Chest freezer (commercial)", 600, "compressor", 3, "Refrigeration"),
    ("Split AC (2 hp)", 2200, "compressor", 4, "HVAC"), ("Cassette AC (3 hp)", 3200, "compressor", 4, "HVAC"),
    ("Borehole pump (1 hp)", 750, "motor", 3, "Pumping"), ("Borehole pump (2 hp)", 1500, "motor", 4, "Pumping"),
    ("Borehole pump (5 hp)", 3750, "motor", 5, "Pumping"), ("Industrial exhaust fan", 750, "motor", 2, "Ventilation"),
    ("Air compressor (2 hp)", 1500, "compressor", 5, "Compressed air"), ("Air compressor (5 hp)", 3750, "compressor", 5, "Compressed air"),
    ("Welding machine (inverter)", 5000, "electronics", 1, "Workshop"), ("Arc welding machine", 9000, "electronics", 1, "Workshop"),
    ("CNC router", 3000, "motor", 3, "Workshop"), ("Lathe machine", 3000, "motor", 4, "Workshop"),
    ("Milling machine", 4000, "motor", 4, "Workshop"), ("Industrial sewing machine", 550, "motor", 2, "Production"),
    ("Packaging machine", 2000, "motor", 3, "Production"), ("Conveyor belt", 1500, "motor", 3, "Production"),
    ("Three-phase motor (7.5 hp)", 5600, "motor", 5, "Motors"), ("Three-phase motor (15 hp)", 11200, "motor", 6, "Motors"),
    ("Electric oven", 6000, "resistive", 1, "Catering"), ("Commercial fryer", 3000, "resistive", 1, "Catering"),
    ("Commercial water heater", 4500, "resistive", 1, "Catering"), ("POS terminal", 15, "electronics", 1, "Retail"),
]


def add_appliances(apps, schema_editor):
    Appliance = apps.get_model("solar", "Appliance")
    for installation_type, rows in (("residential", RESIDENTIAL), ("industrial", INDUSTRIAL)):
        for name, wattage, load_type, surge, category in rows:
            Appliance.objects.update_or_create(
                name=name, installation_type=installation_type,
                defaults={"wattage": Decimal(str(wattage)), "load_type": load_type,
                          "surge_factor": Decimal(str(surge)), "category": category,
                          "starting_type": "possible" if surge > 1 else "single", "popular": True},
            )


class Migration(migrations.Migration):
    dependencies = [("solar", "0013_appliance_installation_type")]
    operations = [migrations.RunPython(add_appliances, migrations.RunPython.noop)]