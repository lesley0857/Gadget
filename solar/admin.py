from django.contrib import admin
from import_export.admin import ImportExportModelAdmin

from .models import (
    Appliance,
    Battery,
    SolarPanel,
    Inverter,
    ChargeController,
    DesignSetting,
    Breaker,
    Cable,
    Fuse,
    SPD,
    Isolator,
    MountingStructure,
    Accessory,
    BOQItem,
)
from .resources import *

@admin.register(Appliance)
class ApplianceAdmin(ImportExportModelAdmin):
    resource_class = ApplianceResource
    list_display = (
        'name',
        'wattage',
        'category',
        'popular'
    )
    search_fields = ('name',)


@admin.register(Battery)
class BatteryAdmin(ImportExportModelAdmin):
    resource_class = BatteryResource
    list_display = (
        'brand',
        'model',
        'battery_type',
        'voltage',
        'capacity_ah',
        'price'
    )
    search_fields = (
        'brand',
        'voltage'
    )


@admin.register(SolarPanel)
class SolarPanelAdmin(ImportExportModelAdmin):
    resource_class = SolarPanelResource
    list_display = (
        'brand',
        'model',
        'power',
        'vmp',
        'imp',
        'price'
    )
    search_fields = (
        'brand',
        'model'
    )

@admin.register(Inverter)
class InverterAdmin(ImportExportModelAdmin):
    resource_class = InverterResource
    list_display = (
        'brand',
        'model',
        'rated_power',
        'dc_voltage',
        'price'
    )
    list_filter = (
        'dc_voltage',
        'brand'
    )

    search_fields = (
        'manufacturer',
        'model'
    )


@admin.register(ChargeController)
class ChargeControllerAdmin(ImportExportModelAdmin):
    resource_class = ChargeControllerResource
    list_display = (
        'brand',
        'model',
        'battery_voltage',
        'max_pv_voltage',
        'max_charge_current'
    )
    list_filter = (
        'battery_voltage',
        'brand',
    )

    search_fields = (
        'brand',
        'model'
    )


####################################################
# CABLES
####################################################

@admin.register(Cable)
class CableAdmin(ImportExportModelAdmin):
    resource_class=CableResource
    list_display = (
        'manufacturer',
        'name',
        'cable_type',
        'size_mm',
        'ampacity',
        'price_per_meter',
        'active'
    )

    list_filter = (
        'cable_type',
        'active'
    )

    search_fields = (
        'manufacturer',
        'name'
    )


####################################################
# FUSES
####################################################

@admin.register(Fuse)
class FuseAdmin(ImportExportModelAdmin):
    resource_class=FuseResource
    list_display = (
        'manufacturer',
        'name',
        'fuse_type',
        'current_rating',
        'voltage_rating',
        'price',
        'active'
    )

    list_filter = (
        'fuse_type',
        'active'
    )

    search_fields = (
        'manufacturer',
        'name'
    )


####################################################
# BREAKERS
####################################################

@admin.register(Breaker)
class BreakerAdmin(ImportExportModelAdmin):
    resource_class=BreakerResource
    list_display = (
        'manufacturer',
        'name',
        'breaker_type',
        'current_rating',
        'voltage_rating',
        'poles',
        'price',
        'active'
    )

    list_filter = (
        'breaker_type',
        'active'
    )

    search_fields = (
        'manufacturer',
        'name'
    )


####################################################
# SPD
####################################################

@admin.register(SPD)
class SPDAdmin(ImportExportModelAdmin):
    resource_class=SPDResource
    list_display = (
        'manufacturer',
        'name',
        'spd_type',
        'voltage_rating',
        'price',
        'active'
    )

    list_filter = (
        'spd_type',
        'active'
    )

    search_fields = (
        'manufacturer',
        'name'
    )


####################################################
# ISOLATORS
####################################################

@admin.register(Isolator)
class IsolatorAdmin(ImportExportModelAdmin):
    resource_class=IsolatorResource
    list_display = (
        'manufacturer',
        'name',
        'isolator_type',
        'current_rating',
        'voltage_rating',
        'price',
        'active'
    )

    list_filter = (
        'isolator_type',
        'active'
    )

    search_fields = (
        'manufacturer',
        'name'
    )


####################################################
# MOUNTING STRUCTURES
####################################################

@admin.register(MountingStructure)
class MountingStructureAdmin(ImportExportModelAdmin):
    resource_class=MountingStructureResource
    list_display = (
        'name',
        'structure_type',
        'panel_capacity',
        'price',
        'active'
    )

    list_filter = (
        'structure_type',
        'active'
    )

    search_fields = (
        'name',
    )


####################################################
# ACCESSORIES
####################################################

@admin.register(Accessory)
class AccessoryAdmin(ImportExportModelAdmin):
    resource_class=AccessoryResource
    list_display = (
        'name',
        'accessory_type',
        'unit',
        'price',
        'active'
    )

    list_filter = (
        'accessory_type',
        'active'
    )

    search_fields = (
        'name',
        'description'
    )


####################################################
# BOQ
####################################################

@admin.register(BOQItem)
class BOQItemAdmin(ImportExportModelAdmin):
    resource_class=BOQItemResource
    list_display = (
        'description',
        'category',
        'unit',
        'unit_price',
        'active'
    )

    list_filter = (
        'category',
        'active'
    )

    search_fields = (
        'description',
    )


####################################################
# SETTINGS
####################################################

@admin.register(DesignSetting)
class DesignSettingAdmin(admin.ModelAdmin):
    list_display = (
        'installation_percentage',
        'profit_percentage',
        'vat_percentage'
    )