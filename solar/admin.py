# solar/admin.py

from django.contrib import admin

from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Appliance,
    # --- deprecated legacy catalog models (remove after data
    # --- migration + second makemigrations, see models.py) ---
    
    # --- new Specification models (OneToOne to ProductListing) ---
    BatterySpecification,
    PanelSpecification,
    InverterSpecification,
    SolarGeneratorSpecification,
    ControllerSpecification,
    CableSpecification,
    FuseSpecification,
    BreakerSpecification,
    SPDSpecification,
    IsolatorSpecification,
    MountingStructureSpecification,
    AccessorySpecification,
    # --- unchanged ---
    DesignSetting,
    BOQItem,
    SolarDesign,
    SolarDesignVersion,
    MaintenanceRecord,
    PerformanceLog,
    FaultReport,
    ServiceRequest,
)

# ================================================================
# PRODUCT SPECIFICATION ADMINS
#
# Commercial fields (name, vendor, price, stock, active, images)
# are edited on ProductListing in the marketplace app — these
# admins only expose the engineering fields, plus a read-only link
# back to the commercial listing.
# ================================================================

class BaseSpecificationAdmin(admin.ModelAdmin):
    """Shared behaviour for every *Specification admin."""

    autocomplete_fields = ("product",)

    @admin.display(description="Product")
    def product_name(self, obj):
        return obj.product.name

    @admin.display(description="Price")
    def product_price(self, obj):
        return obj.product.final_price()

    @admin.display(boolean=True, description="Active")
    def product_active(self, obj):
        return obj.product.is_active


@admin.register(BatterySpecification)
class BatterySpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "battery_type",
        "voltage",
        "capacity_ah",
        "depth_of_discharge",
        "efficiency",
        "max_charge_current",
        "max_discharge_current",
        "hybrid_compatible",
        "cycles",
        "product_price",
        "product_active",
    )
    list_filter = ("battery_type", "hybrid_compatible")
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("product__brand", "product__model_number")


@admin.register(PanelSpecification)
class PanelSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "power",
        "vmp",
        "voc",
        "imp",
        "isc",
        "efficiency",
        "product_price",
        "product_active",
    )
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("power",)


@admin.register(InverterSpecification)
class InverterSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "rated_power",
        "surge_power",
        "dc_voltage",
        "output_voltage",
        "phase",
        "frequency",
        "efficiency",
        "hybrid",
        "product_price",
        "product_active",
    )
    list_filter = ("phase", "hybrid")
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("rated_power",)


@admin.register(SolarGeneratorSpecification)
class SolarGeneratorSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name", "battery_capacity_kwh", "inverter_rated_power",
        "inverter_surge_power", "phase", "hybrid", "product_price", "product_active",
    )
    list_filter = ("phase", "hybrid")
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("inverter_rated_power",)


@admin.register(ControllerSpecification)
class ControllerSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "battery_voltage",
        "max_pv_voltage",
        "max_charge_current",
        "efficiency",
        "product_price",
        "product_active",
    )
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("battery_voltage", "max_charge_current")


@admin.register(CableSpecification)
class CableSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "cable_type",
        "size_mm",
        "ampacity",
        "voltage_rating",
        "product_price",
        "product_active",
    )
    list_filter = ("cable_type",)
    search_fields = ("product__name", "product__brand", "product__model_number")
    ordering = ("cable_type", "size_mm")


@admin.register(FuseSpecification)
class FuseSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "fuse_type",
        "current_rating",
        "voltage_rating",
        "poles",
        "product_price",
        "product_active",
    )
    list_filter = ("fuse_type",)
    search_fields = ("product__name", "product__brand", "product__model_number")


@admin.register(BreakerSpecification)
class BreakerSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "breaker_type",
        "current_rating",
        "voltage_rating",
        "poles",
        "breaking_capacity",
        "product_price",
        "product_active",
    )
    list_filter = ("breaker_type",)
    search_fields = ("product__name", "product__brand", "product__model_number")


@admin.register(SPDSpecification)
class SPDSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "spd_type",
        "voltage_rating",
        "protection_level",
        "product_price",
        "product_active",
    )
    list_filter = ("spd_type",)
    search_fields = ("product__name", "product__brand", "product__model_number")


@admin.register(IsolatorSpecification)
class IsolatorSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "isolator_type",
        "current_rating",
        "voltage_rating",
        "poles",
        "product_price",
        "product_active",
    )
    list_filter = ("isolator_type",)
    search_fields = ("product__name", "product__brand", "product__model_number")


@admin.register(MountingStructureSpecification)
class MountingStructureSpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "structure_type",
        "panel_capacity",
        "product_price",
        "product_active",
    )
    list_filter = ("structure_type",)
    search_fields = ("product__name",)


@admin.register(AccessorySpecification)
class AccessorySpecificationAdmin(BaseSpecificationAdmin):
    list_display = (
        "product_name",
        "accessory_type",
        "unit",
        "product_price",
        "product_active",
    )
    list_filter = ("accessory_type",)
    search_fields = ("product__name",)
# ================================================================
# GENERIC CSV RESOURCE
# ================================================================

def make_resource(model_class):
    class DynamicResource(resources.ModelResource):

        class Meta:
            model = model_class
            exclude = ("id",)
            skip_unchanged = True
            report_skipped = True

    return DynamicResource


# ================================================================
# COMMON ADMIN HELPERS
# ================================================================

class ActiveStatusFilter(admin.SimpleListFilter):
    title = "active status"
    parameter_name = "active_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "Active"),
            ("inactive", "Inactive"),
        )

    def queryset(self, request, queryset):

        if self.value() == "active":
            return queryset.filter(active=True)

        if self.value() == "inactive":
            return queryset.filter(active=False)

        return queryset


# ================================================================
# APPLIANCE
# ================================================================

@admin.register(Appliance)
class ApplianceAdmin(ImportExportModelAdmin):

    resource_class = make_resource(Appliance)

    list_display = (
        "name",
        "wattage",
        "surge_factor",
        "load_type",
        "starting_type",
        "category",
        "popular",
    )

    list_filter = (
        "load_type",
        "starting_type",
        "category",
        "popular",
    )

    search_fields = (
        "name",
        "category",
    )

    list_editable = (
        "wattage",
        "surge_factor",
        "popular",
    )

    ordering = (
        "category",
        "name",
    )

    fieldsets = (
        (
            "Appliance Identity",
            {
                "fields": (
                    "name",
                    "category",
                )
            },
        ),
        (
            "Electrical Characteristics",
            {
                "fields": (
                    "wattage",
                    "surge_factor",
                    "load_type",
                    "starting_type",
                ),
                "description": (
                    "These values form the engineering defaults "
                    "used by the load engine."
                ),
            },
        ),
        (
            "Catalog Settings",
            {
                "fields": (
                    "popular",
                )
            },
        ),
    )


# ================================================================
# DESIGN SETTINGS
# ================================================================

@admin.register(DesignSetting)
class DesignSettingAdmin(ImportExportModelAdmin):

    resource_class = make_resource(DesignSetting)

    list_display = (
        "name",
        "peak_sun_hours",
        "performance_ratio",
        "future_expansion",
        "installation_percentage",
        "profit_percentage",
        "vat_percentage",
    )

    search_fields = (
        "name",
    )

    fieldsets = (
        (
            "Profile",
            {
                "fields": (
                    "name",
                )
            },
        ),
        (
            "Solar Resource",
            {
                "fields": (
                    "peak_sun_hours",
                    "performance_ratio",
                )
            },
        ),
        (
            "Design Margins",
            {
                "fields": (
                    "future_expansion",
                )
            },
        ),
        (
            "Commercial Settings",
            {
                "fields": (
                    "installation_percentage",
                    "profit_percentage",
                    "vat_percentage",
                )
            },
        ),
    )


# ================================================================
# BOQ ITEM
# ================================================================

@admin.register(BOQItem)
class BOQItemAdmin(ImportExportModelAdmin):

    resource_class = make_resource(BOQItem)

    list_display = (
        "description",
        "category",
        "unit",
        "unit_price",
        "active",
    )

    list_filter = (
        "category",
        "active",
        ActiveStatusFilter,
    )

    search_fields = (
        "description",
    )

    list_editable = (
        "unit_price",
        "active",
    )

    ordering = (
        "category",
        "description",
    )

    fieldsets = (
        (
            "BOQ Item",
            {
                "fields": (
                    "description",
                    "category",
                    "unit",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "unit_price",
                    "active",
                )
            },
        ),
    )


# ================================================================
# SOLAR DESIGN
# ================================================================

@admin.register(SolarDesign)
class SolarDesignAdmin(ImportExportModelAdmin):

    resource_class = make_resource(SolarDesign)

    list_display = (
        "project_name",
        "client_name",
        "operating_mode",
        "peak_sun_hours",
        "status",
        "design_complete_display",
        "favorite",
        "archived",
        "created_at",
    )

    list_filter = (
        "operating_mode",
        "status",
        "favorite",
        "archived",
    )

    search_fields = (
        "project_name",
        "client_name",
        "project_location",
        "description",
        "user__username",
        "user__email",
    )

    autocomplete_fields = (
        "user",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "total_cost_display",
        "installed_array_power_display",
        "battery_storage_display",
        "design_complete_display",
        "load_result",
        "voltage_result",
        "battery_result",
        "panel_result",
        "controller_result",
        "inverter_result",
        "protection_result",
        "cable_result",
        "accessory_result",
        "boq_result",
        "pricing_result",
    )

    date_hierarchy = "created_at"

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Ownership",
            {
                "fields": (
                    "user",
                )
            },
        ),
        (
            "Project Information",
            {
                "fields": (
                    "project_name",
                    "client_name",
                    "project_location",
                    "description",
                )
            },
        ),
        (
            "Design Parameters",
            {
                "fields": (
                    "operating_mode",
                    "peak_sun_hours",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "favorite",
                    "archived",
                )
            },
        ),
        (
            "Design Summary",
            {
                "fields": (
                    "total_cost_display",
                    "installed_array_power_display",
                    "battery_storage_display",
                    "design_complete_display",
                )
            },
        ),
        (
            "Engine Results",
            {
                "fields": (
                    "load_result", "voltage_result", "battery_result", "panel_result",
                    "controller_result", "inverter_result", "protection_result",
                    "cable_result", "accessory_result", "boq_result", "pricing_result",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(
        boolean=True,
        description="Complete",
    )
    def design_complete_display(self, obj):
        return obj.design_complete

    @admin.display(
        description="Total Cost",
    )
    def total_cost_display(self, obj):
        return obj.total_cost

    @admin.display(
        description="Installed PV",
    )
    def installed_array_power_display(self, obj):
        return f"{obj.installed_array_power} W"

    @admin.display(
        description="Battery Storage",
    )
    def battery_storage_display(self, obj):
        return f"{obj.battery_storage} Wh"


# ================================================================
# DESIGN VERSION
# ================================================================

@admin.register(SolarDesignVersion)
class SolarDesignVersionAdmin(ImportExportModelAdmin):

    resource_class = make_resource(SolarDesignVersion)

    list_display = (
        "design",
        "version",
        "created_by",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "design__project_name",
        "design__client_name",
        "created_by__username",
        "created_by__email",
    )

    autocomplete_fields = (
        "design",
        "created_by",
    )

    readonly_fields = (
        "created_at",
        "load_result",
        "voltage_result",
        "battery_result",
        "panel_result",
        "controller_result",
        "inverter_result",
        "protection_result",
        "cable_result",
        "accessory_result",
        "boq_result",
        "pricing_result",
    )

    ordering = (
        "-version",
    )

    fieldsets = (
        (
            "Version",
            {
                "fields": (
                    "design",
                    "version",
                    "created_by",
                    "created_at",
                )
            },
        ),
        (
            "Engine Snapshot",
            {
                "fields": (
                    "load_result",
                    "voltage_result",
                    "battery_result",
                    "panel_result",
                    "controller_result",
                    "inverter_result",
                    "protection_result",
                    "cable_result",
                    "accessory_result",
                    "boq_result",
                    "pricing_result",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )


# ================================================================
# MAINTENANCE RECORD
# ================================================================

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(ImportExportModelAdmin):

    resource_class = make_resource(MaintenanceRecord)

    list_display = (
        "design",
        "service_date",
        "technician",
        "service_type",
        "next_service_date",
    )

    list_filter = (
        "service_type",
        "service_date",
    )

    search_fields = (
        "design__project_name",
        "design__client_name",
        "technician",
        "service_type",
        "findings",
        "corrective_action",
    )

    autocomplete_fields = (
        "design",
    )

    date_hierarchy = "service_date"

    ordering = (
        "-service_date",
    )


# ================================================================
# PERFORMANCE LOG
# ================================================================

@admin.register(PerformanceLog)
class PerformanceLogAdmin(ImportExportModelAdmin):

    resource_class = make_resource(PerformanceLog)

    list_display = (
        "design",
        "timestamp",
        "battery_voltage",
        "battery_current",
        "pv_voltage",
        "pv_current",
        "inverter_output",
        "load_power",
    )

    list_filter = (
        "timestamp",
    )

    search_fields = (
        "design__project_name",
        "remarks",
    )

    autocomplete_fields = (
        "design",
    )

    readonly_fields = (
        "timestamp",
    )

    date_hierarchy = "timestamp"

    ordering = (
        "-timestamp",
    )


# ================================================================
# FAULT REPORT
# ================================================================

@admin.register(FaultReport)
class FaultReportAdmin(ImportExportModelAdmin):

    resource_class = make_resource(FaultReport)

    list_display = (
        "title",
        "design",
        "severity",
        "status",
        "reported_by",
        "reported_at",
        "resolved_at",
    )

    list_filter = (
        "severity",
        "status",
        "reported_at",
    )

    search_fields = (
        "title",
        "description",
        "resolution",
        "design__project_name",
        "reported_by__username",
        "reported_by__email",
    )

    autocomplete_fields = (
        "design",
        "reported_by",
    )

    readonly_fields = (
        "reported_at",
    )

    date_hierarchy = "reported_at"

    ordering = (
        "-reported_at",
    )


# ================================================================
# SERVICE REQUEST
# ================================================================

@admin.register(ServiceRequest)
class ServiceRequestAdmin(ImportExportModelAdmin):

    resource_class = make_resource(ServiceRequest)

    list_display = (
        "subject",
        "design",
        "customer",
        "priority",
        "status",
        "assigned_to",
        "scheduled_date",
        "completed_date",
        "created_at",
    )

    list_filter = (
        "priority",
        "status",
        "scheduled_date",
        "completed_date",
    )

    search_fields = (
        "subject",
        "description",
        "design__project_name",
        "customer__username",
        "customer__email",
        "assigned_to__username",
        "assigned_to__email",
    )

    autocomplete_fields = (
        "design",
        "customer",
        "assigned_to",
    )

    readonly_fields = (
        "created_at",
    )

    date_hierarchy = "created_at"

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "design",
                    "customer",
                    "subject",
                    "description",
                )
            },
        ),
        (
            "Workflow",
            {
                "fields": (
                    "priority",
                    "status",
                    "assigned_to",
                    "scheduled_date",
                    "completed_date",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                )
            },
        ),
    )

