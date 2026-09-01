# solar/models.py
#
# ================================================================
# INTEGRATION NOTE — READ BEFORE APPLYING
# ================================================================
#
# Every model that used to carry its OWN commercial fields
# (brand, model, price, active) has been converted into a
# "*Specification" model holding ONLY engineering data, linked
# 1:1 to the marketplace's ProductListing, which now owns all
# commercial data (name, vendor, price, stock, images, active).
#
# REPLACE "marketplace" BELOW WITH YOUR ACTUAL APP LABEL
# (the app that contains ProductListing) if it isn't "marketplace".
# It appears once, as PRODUCT_LISTING_MODEL, and is referenced by
# every OneToOneField below.
#
# Appliance, DesignSetting and BOQItem are UNCHANGED — they are not
# physical catalog products (Appliance is load-profile reference
# data; BOQItem is a generic labour/material line; DesignSetting is
# a commercial-settings profile). They can be integrated later the
# same way if you decide they should also be sellable listings.
#
# ================================================================

from django.db import models
from django.conf import settings

PRODUCT_LISTING_MODEL = "catalog.ProductListing"  # <-- confirm/adjust


# ================================================================
# APPLIANCES (unchanged — load-profile reference data, not a
# sellable catalog item)
# ================================================================

class Appliance(models.Model):

    INSTALLATION_TYPES = (
        ("residential", "Residential"),
        ("industrial", "Industrial / Commercial"),
    )

    LOAD_TYPES = (
        ("resistive", "Resistive"),
        ("motor", "Motor"),
        ("compressor", "Compressor"),
        ("electronics", "Electronics"),
        ("lighting", "Lighting"),
    )

    STARTING_TYPES = (
        ("single", "Starts alone"),
        ("possible", "May start together"),
        ("simultaneous", "Can start simultaneously"),
    )

    name = models.CharField(max_length=100)

    wattage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    surge_factor = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    load_type = models.CharField(
        max_length=20,
        choices=LOAD_TYPES,
        default="resistive",
    )

    starting_type = models.CharField(
        max_length=20,
        choices=STARTING_TYPES,
        default="single",
    )

    category = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    installation_type = models.CharField(
        max_length=20,
        choices=INSTALLATION_TYPES,
        default="residential",
        db_index=True,
        help_text="Where this typical appliance load is normally used.",
    )

    popular = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.wattage}W)"


# ================================================================
# BATTERY SPECIFICATION
# ================================================================

class BatterySpecification(models.Model):

    BATTERY_TYPES = (
        ("lead_acid", "Lead Acid"),
        ("lithium", "Lithium"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="battery_spec",
    )

    battery_type = models.CharField(
        max_length=20,
        choices=BATTERY_TYPES,
    )

    voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
    )

    capacity_ah = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    depth_of_discharge = models.DecimalField(
        max_digits=6,
        decimal_places=3,
    )

    efficiency = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.90,
    )

    max_discharge_current = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    max_charge_current = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    cycles = models.PositiveIntegerField(default=3000)

    warranty_years = models.PositiveIntegerField(default=5)

    hybrid_compatible = models.BooleanField(
        default=False,
        help_text="Suitable for use with a hybrid inverter system.",
    )

    weight = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    def __str__(self):
        return (
            f"Battery spec — {self.product.name} "
            f"{self.voltage}V {self.capacity_ah}Ah"
        )


# ================================================================
# SOLAR PANEL SPECIFICATION
# ================================================================

class PanelSpecification(models.Model):

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="panel_spec",
    )

    power = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    vmp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    voc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    imp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    isc = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    efficiency = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.21,
    )

    def __str__(self):
        return f"Panel spec — {self.product.name} {self.power}W"


# ================================================================
# INVERTER SPECIFICATION
# ================================================================

class InverterSpecification(models.Model):

    PHASES = (
        ("single_phase", "Single Phase"),
        ("three_phase", "Three Phase"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="inverter_spec",
    )

    rated_power = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    surge_power = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    dc_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
    )

    output_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=230,
    )

    frequency = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=50,
    )

    phase = models.CharField(
        max_length=20,
        choices=PHASES,
        default="single_phase",
    )

    efficiency = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.95,
    )

    hybrid = models.BooleanField(default=False)

    def __str__(self):
        return f"Inverter spec — {self.product.name} {self.rated_power}W"


class SolarGeneratorSpecification(models.Model):
    """An all-in-one solar generator sold through ProductListing."""

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="solar_generator_spec",
    )
    battery_capacity_kwh = models.DecimalField(max_digits=8, decimal_places=2)
    inverter_rated_power = models.DecimalField(max_digits=12, decimal_places=2)
    inverter_surge_power = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    output_voltage = models.DecimalField(max_digits=8, decimal_places=2, default=230)
    phase = models.CharField(max_length=20, choices=InverterSpecification.PHASES, default="single_phase")
    hybrid = models.BooleanField(default=True)

    def __str__(self):
        return f"Solar generator — {self.product.name}"


# ================================================================
# CHARGE CONTROLLER SPECIFICATION
# ================================================================

class ControllerSpecification(models.Model):

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="controller_spec",
    )

    battery_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
    )

    max_pv_voltage = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    max_charge_current = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    efficiency = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.98,
    )

    def __str__(self):
        return (
            f"Controller spec — {self.product.name} "
            f"{self.max_charge_current}A"
        )


# ================================================================
# DESIGN SETTINGS (unchanged)
# ================================================================

class DesignSetting(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    peak_sun_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=5,
    )

    performance_ratio = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=0.75,
    )

    future_expansion = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=1.20,
    )

    installation_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=10,
    )

    profit_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=15,
    )

    vat_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=7.5,
    )

    def __str__(self):
        return self.name


# ================================================================
# CABLE SPECIFICATION
# ================================================================

class CableSpecification(models.Model):

    CABLE_TYPES = (
        ("pv", "PV Cable"),
        ("battery", "Battery Cable"),
        ("ac", "AC Cable"),
        ("earth", "Earth Cable"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="cable_spec",
    )

    cable_type = models.CharField(
        max_length=20,
        choices=CABLE_TYPES,
    )

    size_mm = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    ampacity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    voltage_rating = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"Cable spec — {self.product.name} {self.size_mm}mm²"


# ================================================================
# FUSE SPECIFICATION
# ================================================================

class FuseSpecification(models.Model):

    FUSE_TYPES = (
        ("pv", "PV Fuse"),
        ("battery", "Battery Fuse"),
        ("ac", "AC Fuse"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="fuse_spec",
    )

    fuse_type = models.CharField(
        max_length=20,
        choices=FUSE_TYPES,
    )

    current_rating = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    voltage_rating = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    poles = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"Fuse spec — {self.product.name} {self.current_rating}A"


# ================================================================
# BREAKER SPECIFICATION
# ================================================================

class BreakerSpecification(models.Model):

    BREAKER_TYPES = (
        ("ac", "AC Breaker"),
        ("dc", "DC Breaker"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="breaker_spec",
    )

    breaker_type = models.CharField(
        max_length=20,
        choices=BREAKER_TYPES,
    )

    current_rating = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    voltage_rating = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    poles = models.PositiveIntegerField()

    breaking_capacity = models.PositiveIntegerField(default=6000)

    def __str__(self):
        return f"Breaker spec — {self.product.name} {self.current_rating}A"


# ================================================================
# SPD SPECIFICATION
# ================================================================

class SPDSpecification(models.Model):

    SPD_TYPES = (
        ("ac", "AC SPD"),
        ("dc", "DC SPD"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="spd_spec",
    )

    spd_type = models.CharField(
        max_length=20,
        choices=SPD_TYPES,
    )

    voltage_rating = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    protection_level = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"SPD spec — {self.product.name} {self.voltage_rating}V"


# ================================================================
# ISOLATOR SPECIFICATION
# ================================================================

class IsolatorSpecification(models.Model):

    ISOLATOR_TYPES = (
        ("ac", "AC Isolator"),
        ("dc", "DC Isolator"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="isolator_spec",
    )

    isolator_type = models.CharField(
        max_length=20,
        choices=ISOLATOR_TYPES,
    )

    current_rating = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    voltage_rating = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    poles = models.PositiveIntegerField()

    def __str__(self):
        return f"Isolator spec — {self.product.name} {self.current_rating}A"


# ================================================================
# MOUNTING STRUCTURE SPECIFICATION
# ================================================================

class MountingStructureSpecification(models.Model):

    TYPES = (
        ("roof", "Roof Mount"),
        ("ground", "Ground Mount"),
        ("carport", "Carport"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="mounting_structure_spec",
    )

    structure_type = models.CharField(
        max_length=20,
        choices=TYPES,
    )

    panel_capacity = models.PositiveIntegerField()

    def __str__(self):
        return f"Mounting spec — {self.product.name}"


# ================================================================
# ACCESSORY SPECIFICATION
# ================================================================

class AccessorySpecification(models.Model):

    ACCESSORY_TYPES = (
        ("bolt", "Bolt"),
        ("nut", "Nut"),
        ("washer", "Washer"),
        ("hanger", "Hanger"),
        ("rail", "Rail"),
        ("lug", "Cable Lug"),
        ("gland", "Cable Gland"),
        ("connector", "MC4 Connector"),
        ("trunking", "Trunking"),
        ("conduit", "Conduit"),
        ("clamp", "Panel Clamp"),
        ("earthing", "Earthing Material"),
        ("battery_rack", "Battery Rack"),
        ("other", "Other"),
    )

    product = models.OneToOneField(
        PRODUCT_LISTING_MODEL,
        on_delete=models.CASCADE,
        related_name="accessory_spec",
    )

    accessory_type = models.CharField(
        max_length=30,
        choices=ACCESSORY_TYPES,
        default="other",
    )

    unit = models.CharField(max_length=20, default="pcs")

    def __str__(self):
        return f"Accessory spec — {self.product.name}"


# ================================================================
# BOQ ITEMS (unchanged — generic labour/material line, not a
# physical catalog product)
# ================================================================

class BOQItem(models.Model):

    CATEGORY = (
        ("material", "Material"),
        ("labour", "Labour"),
        ("transport", "Transport"),
    )

    description = models.CharField(max_length=300)

    category = models.CharField(
        max_length=20,
        choices=CATEGORY,
    )

    unit = models.CharField(max_length=20, default="pcs")

    unit_price = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    active = models.BooleanField(default=True)

    def __str__(self):
        return self.description


# ================================================================
# SOLAR DESIGN
# ================================================================

class SolarDesign(models.Model):

    OPERATING_MODES = (
        ("off_grid", "Off Grid"),
        ("hybrid", "Hybrid"),
        ("grid_tied", "Grid Tied"),
    )

    INSTALLATION_TYPES = (
        ("residential", "Residential"),
        ("industrial", "Industrial / Commercial"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("designed", "Designed"),
        ("quoted", "Quoted"),
        ("approved", "Approved"),
        ("installed", "Installed"),
        ("commissioned", "Commissioned"),
        ("completed", "Completed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solar_designs",
    )

    project_name = models.CharField(max_length=255)

    client_name = models.CharField(
        max_length=255,
        blank=True,
    )

    project_location = models.CharField(
        max_length=255,
        blank=True,
    )

    description = models.TextField(blank=True)

    operating_mode = models.CharField(
        max_length=30,
        choices=OPERATING_MODES,
        default="off_grid",
    )

    installation_type = models.CharField(
        max_length=20,
        choices=INSTALLATION_TYPES,
        default="residential",
    )

    peak_sun_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=5,
    )

    autonomy_days = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=1,
    )

    load_result = models.JSONField(default=dict, blank=True)
    voltage_result = models.JSONField(default=dict, blank=True)
    battery_result = models.JSONField(default=dict, blank=True)
    panel_result = models.JSONField(default=dict, blank=True)
    controller_result = models.JSONField(default=dict, blank=True)
    inverter_result = models.JSONField(default=dict, blank=True)
    protection_result = models.JSONField(default=dict, blank=True)
    cable_result = models.JSONField(default=dict, blank=True)
    accessory_result = models.JSONField(default=dict, blank=True)
    boq_result = models.JSONField(default=dict, blank=True)
    pricing_result = models.JSONField(default=dict, blank=True)
    warnings_result = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
    )

    favorite = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.project_name

    @property
    def total_cost(self):
        return self.pricing_result.get("grand_total", 0)

    @property
    def design_complete(self):
        return all([
            bool(self.load_result),
            bool(self.voltage_result),
            bool(self.battery_result),
            bool(self.panel_result),
            bool(self.controller_result),
            bool(self.inverter_result),
            bool(self.protection_result),
            bool(self.cable_result),
            bool(self.accessory_result),
            bool(self.boq_result),
            bool(self.pricing_result),
        ])


# ================================================================
# SOLAR DESIGN VERSION
# ================================================================

class SolarDesignVersion(models.Model):

    design = models.ForeignKey(
        SolarDesign,
        on_delete=models.CASCADE,
        related_name="versions",
    )

    version = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    load_result = models.JSONField(default=dict)
    voltage_result = models.JSONField(default=dict)
    battery_result = models.JSONField(default=dict)
    panel_result = models.JSONField(default=dict)
    controller_result = models.JSONField(default=dict)
    inverter_result = models.JSONField(default=dict)
    protection_result = models.JSONField(default=dict)
    cable_result = models.JSONField(default=dict)
    accessory_result = models.JSONField(default=dict)
    boq_result = models.JSONField(default=dict)
    pricing_result = models.JSONField(default=dict)
    warnings_result = models.JSONField(default=dict)

    class Meta:
        ordering = ["-version"]
        unique_together = ("design", "version")

    def __str__(self):
        return f"{self.design.project_name} V{self.version}"


# ================================================================
# MAINTENANCE RECORD
# ================================================================

class MaintenanceRecord(models.Model):
    """
    Stores maintenance/service history for an installed solar system.
    """

    design = models.ForeignKey(
        SolarDesign,
        on_delete=models.CASCADE,
        related_name="maintenance_records",
    )

    service_date = models.DateField()

    technician = models.CharField(
        max_length=200,
    )

    service_type = models.CharField(
        max_length=100,
    )

    findings = models.TextField(
        blank=True,
    )

    corrective_action = models.TextField(
        blank=True,
    )

    next_service_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return (
            f"{self.design.project_name} - "
            f"{self.service_date}"
        )

    class Meta:
        ordering = [
            "-service_date",
            "-created_at",
        ]
        verbose_name = "Maintenance Record"
        verbose_name_plural = "Maintenance Records"


# ================================================================
# PERFORMANCE LOG
# ================================================================

class PerformanceLog(models.Model):
    """
    Stores operational/performance measurements from an installed
    solar system.
    """

    design = models.ForeignKey(
        SolarDesign,
        on_delete=models.CASCADE,
        related_name="performance_logs",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
    )

    battery_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    battery_current = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    pv_voltage = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    pv_current = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    inverter_output = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    load_power = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    remarks = models.TextField(
        blank=True,
    )

    def __str__(self):
        return (
            f"{self.design.project_name} - "
            f"{self.timestamp}"
        )

    class Meta:
        ordering = [
            "-timestamp",
        ]
        verbose_name = "Performance Log"
        verbose_name_plural = "Performance Logs"


# ================================================================
# FAULT REPORT
# ================================================================

class FaultReport(models.Model):
    """
    Records faults/problems reported against an installed solar
    system.
    """

    SEVERITY = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )

    STATUS = (
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    )

    design = models.ForeignKey(
        SolarDesign,
        on_delete=models.CASCADE,
        related_name="fault_reports",
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_solar_faults",
    )

    title = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY,
        default="medium",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="open",
    )

    reported_at = models.DateTimeField(
        auto_now_add=True,
    )

    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    resolution = models.TextField(
        blank=True,
    )

    def __str__(self):
        return self.title

    class Meta:
        ordering = [
            "-reported_at",
        ]
        verbose_name = "Fault Report"
        verbose_name_plural = "Fault Reports"


# ================================================================
# SERVICE REQUEST
# ================================================================

class ServiceRequest(models.Model):
    """
    Customer/service workflow for an installed solar system.
    """

    PRIORITY = (
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    )

    STATUS = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    design = models.ForeignKey(
        SolarDesign,
        on_delete=models.CASCADE,
        related_name="service_requests",
    )

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solar_service_requests",
    )

    subject = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY,
        default="normal",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="pending",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="assigned_service_requests",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    scheduled_date = models.DateField(
        null=True,
        blank=True,
    )

    completed_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.subject

    class Meta:
        ordering = [
            "-created_at",
        ]
        verbose_name = "Service Request"
        verbose_name_plural = "Service Requests"

class EarthingDesign(models.Model):
    """Persisted standalone or solar-linked earthing engineering assessment."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="earthing_designs")
    solar_design = models.ForeignKey("solar.SolarDesign", null=True, blank=True, on_delete=models.SET_NULL, related_name="earthing_assessments")
    project_name = models.CharField(max_length=255)
    installation_type = models.CharField(max_length=30, default="industrial")
    standard = models.CharField(max_length=100, blank=True)
    inputs = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"Earthing — {self.project_name}"