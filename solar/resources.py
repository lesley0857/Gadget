from import_export import resources

from .models import (
    Appliance,
    Battery,
    SolarPanel,
    Inverter,
    ChargeController,
    Cable,
    Fuse,
    Breaker,
    SPD,
    Isolator,
    MountingStructure,
    Accessory,
    BOQItem,
)


class ApplianceResource(resources.ModelResource):
    class Meta:
        model = Appliance


class BatteryResource(resources.ModelResource):
    class Meta:
        model = Battery


class SolarPanelResource(resources.ModelResource):
    class Meta:
        model = SolarPanel


class InverterResource(resources.ModelResource):
    class Meta:
        model = Inverter


class ChargeControllerResource(resources.ModelResource):
    class Meta:
        model = ChargeController


class CableResource(resources.ModelResource):
    class Meta:
        model = Cable


class FuseResource(resources.ModelResource):
    class Meta:
        model = Fuse


class BreakerResource(resources.ModelResource):
    class Meta:
        model = Breaker


class SPDResource(resources.ModelResource):
    class Meta:
        model = SPD


class IsolatorResource(resources.ModelResource):
    class Meta:
        model = Isolator


class MountingStructureResource(resources.ModelResource):
    class Meta:
        model = MountingStructure


class AccessoryResource(resources.ModelResource):
    class Meta:
        model = Accessory


class BOQItemResource(resources.ModelResource):
    class Meta:
        model = BOQItem