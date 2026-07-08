from django.db import models


#################################################
# APPLIANCES
#################################################

class Appliance(models.Model):

    CATEGORY_CHOICES = (
        ('lighting', 'Lighting'),
        ('cooling', 'Cooling'),
        ('electronics', 'Electronics'),
        ('kitchen', 'Kitchen'),
        ('industrial', 'Industrial'),
        ('other', 'Other'),
    )

    name = models.CharField(max_length=100)

    wattage = models.FloatField()

    surge_factor = models.FloatField(default=1)

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='other'
    )

    popular = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.wattage}W)"


#################################################
# BATTERIES
#################################################

class Battery(models.Model):

    BATTERY_TYPES = (
        ('lead_acid', 'Lead Acid'),
        ('lithium', 'Lithium'),
    )

    brand = models.CharField(max_length=100)

    model = models.CharField(max_length=100)

    battery_type = models.CharField(
        max_length=20,
        choices=BATTERY_TYPES
    )

    voltage = models.FloatField()

    capacity_ah = models.FloatField()

    depth_of_discharge = models.FloatField(
        help_text="0.5 for lead acid, 0.95 for lithium"
    )

    efficiency = models.FloatField(
        default=0.90
    )

    cycles = models.IntegerField(
        default=3000
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.brand} "
            f"{self.model} "
            f"{self.voltage}V "
            f"{self.capacity_ah}Ah"
        )


#################################################
# SOLAR PANELS
#################################################

class SolarPanel(models.Model):

    brand = models.CharField(max_length=100)

    model = models.CharField(max_length=100)

    power = models.FloatField()

    vmp = models.FloatField()

    voc = models.FloatField()

    imp = models.FloatField()

    isc = models.FloatField()

    efficiency = models.FloatField(
        default=0.21
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.brand} "
            f"{self.model} "
            f"{self.power}W"
        )


#################################################
# INVERTERS
#################################################

class Inverter(models.Model):

    brand = models.CharField(max_length=100)

    model = models.CharField(max_length=100)

    rated_power = models.FloatField()

    surge_power = models.FloatField()

    dc_voltage = models.IntegerField()

    efficiency = models.FloatField(
        default=0.95
    )

    hybrid = models.BooleanField(
        default=False
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.brand} "
            f"{self.model} "
            f"{self.rated_power}W"
        )


#################################################
# MPPT CONTROLLERS
#################################################

class ChargeController(models.Model):

    brand = models.CharField(max_length=100)

    model = models.CharField(max_length=100)

    battery_voltage = models.IntegerField()

    max_pv_voltage = models.FloatField()

    max_charge_current = models.FloatField()

    efficiency = models.FloatField(
        default=0.98
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.brand} "
            f"{self.model} "
            f"{self.max_charge_current}A"
        )


#################################################
# DESIGN SETTINGS
#################################################

class DesignSetting(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    peak_sun_hours = models.FloatField(
        default=5
    )

    performance_ratio = models.FloatField(
        default=0.75
    )

    future_expansion = models.FloatField(
        default=1.2
    )

    installation_percentage = models.FloatField(
        default=10
    )

    profit_percentage = models.FloatField(
        default=15
    )

    vat_percentage = models.FloatField(
        default=7.5
    )

    def __str__(self):
        return self.name
    

##############################################
# CABLES
##############################################

class Cable(models.Model):

    CABLE_TYPES = (
        ('pv', 'PV Cable'),
        ('battery', 'Battery Cable'),
        ('ac', 'AC Cable'),
        ('earth', 'Earth Cable'),
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    name = models.CharField(
        max_length=100
    )

    cable_type = models.CharField(
        max_length=20,
        choices=CABLE_TYPES
    )

    size_mm = models.FloatField()

    ampacity = models.FloatField()

    voltage_rating = models.IntegerField(
        blank=True,
        null=True
    )

    price_per_meter = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    created = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.name} "
            f"{self.size_mm}mm²"
        )

##############################################
# FUSES
##############################################

class Fuse(models.Model):

    FUSE_TYPES = (
        ('pv', 'PV Fuse'),
        ('battery', 'Battery Fuse'),
        ('ac', 'AC Fuse'),
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    name = models.CharField(
        max_length=100
    )

    fuse_type = models.CharField(
        max_length=20,
        choices=FUSE_TYPES
    )

    current_rating = models.FloatField()

    voltage_rating = models.FloatField()

    poles = models.IntegerField(
        default=1
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.name} "
            f"{self.current_rating}A"
        )

##############################################
# BREAKERS
##############################################

class Breaker(models.Model):

    BREAKER_TYPES = (
        ('ac', 'AC Breaker'),
        ('dc', 'DC Breaker'),
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    name = models.CharField(
        max_length=100
    )

    breaker_type = models.CharField(
        max_length=20,
        choices=BREAKER_TYPES
    )

    current_rating = models.FloatField()

    voltage_rating = models.FloatField()

    poles = models.IntegerField()

    breaking_capacity = models.IntegerField(
        default=6000
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.name} "
            f"{self.current_rating}A"
        )

##############################################
# SURGE PROTECTION
##############################################

class SPD(models.Model):

    SPD_TYPES = (
        ('ac', 'AC SPD'),
        ('dc', 'DC SPD'),
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    name = models.CharField(
        max_length=100
    )

    spd_type = models.CharField(
        max_length=20,
        choices=SPD_TYPES
    )

    voltage_rating = models.FloatField()

    protection_level = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.name} "
            f"{self.voltage_rating}V"
        )

##############################################
# ISOLATORS
##############################################

class Isolator(models.Model):

    ISOLATOR_TYPES = (
        ('ac', 'AC Isolator'),
        ('dc', 'DC Isolator'),
    )

    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    name = models.CharField(
        max_length=100
    )

    isolator_type = models.CharField(
        max_length=20,
        choices=ISOLATOR_TYPES
    )

    current_rating = models.FloatField()

    voltage_rating = models.FloatField()

    poles = models.IntegerField()

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return (
            f"{self.name} "
            f"{self.current_rating}A"
        )
    
##############################################
# MOUNTING STRUCTURES
##############################################

class MountingStructure(models.Model):

    TYPES = (
        ('roof', 'Roof Mount'),
        ('ground', 'Ground Mount'),
        ('carport', 'Carport'),
    )

    name = models.CharField(
        max_length=100
    )

    structure_type = models.CharField(
        max_length=20,
        choices=TYPES
    )

    panel_capacity = models.IntegerField()

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return self.name
    
##############################################
# ACCESSORIES
##############################################

class Accessory(models.Model):

    ACCESSORY_TYPES = (

        ('bolt', 'Bolt'),

        ('nut', 'Nut'),

        ('washer', 'Washer'),

        ('hanger', 'Hanger'),

        ('rail', 'Rail'),

        ('lug', 'Cable Lug'),

        ('gland', 'Cable Gland'),

        ('connector', 'MC4 Connector'),

        ('trunking', 'Trunking'),

        ('conduit', 'Conduit'),

        ('clamp', 'Panel Clamp'),

        ('earthing', 'Earthing Material'),

        ('battery_rack', 'Battery Rack'),

        ('other', 'Other'),
    )

    name = models.CharField(
        max_length=200
    )

    accessory_type = models.CharField(
        max_length=30,
        choices=ACCESSORY_TYPES,
        default='other'
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    unit = models.CharField(
        max_length=20,
        default='pcs'
    )

    price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    created = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.name}"
        )
    
##############################################
# BOQ ITEMS
##############################################

class BOQItem(models.Model):

    CATEGORY = (
        ('material', 'Material'),
        ('labour', 'Labour'),
        ('transport', 'Transport'),
    )

    description = models.CharField(
        max_length=300
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY
    )

    unit = models.CharField(
        max_length=20,
        default='pcs'
    )

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return self.description