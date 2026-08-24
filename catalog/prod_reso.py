"""CSV import/export resources for marketplace products and solar specs."""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from accounts.models import Vendor
from solar.models import (
    AccessorySpecification, BatterySpecification, BreakerSpecification,
    CableSpecification, ControllerSpecification, FuseSpecification,
    InverterSpecification, IsolatorSpecification,
    MountingStructureSpecification, PanelSpecification, SPDSpecification,
)

from .models import Category, ProductListing


# Each row uses specification_type plus the matching prefixed columns, e.g.
# ``battery`` + ``battery_voltage``. Other specification columns are ignored.
SPECIFICATIONS = {
    "battery": (BatterySpecification, "battery_spec", {
        "battery_type": "battery_type", "voltage": "voltage", "capacity_ah": "capacity_ah",
        "depth_of_discharge": "depth_of_discharge", "efficiency": "efficiency",
        "max_discharge_current": "max_discharge_current", "max_charge_current": "max_charge_current",
        "cycles": "cycles", "warranty_years": "warranty_years", "weight": "weight",
    }),
    "panel": (PanelSpecification, "panel_spec", {
        "power": "power", "vmp": "vmp", "voc": "voc", "imp": "imp", "isc": "isc", "efficiency": "efficiency",
    }),
    "inverter": (InverterSpecification, "inverter_spec", {
        "rated_power": "rated_power", "surge_power": "surge_power", "dc_voltage": "dc_voltage",
        "output_voltage": "output_voltage", "frequency": "frequency", "phase": "phase",
        "efficiency": "efficiency", "hybrid": "hybrid",
    }),
    "controller": (ControllerSpecification, "controller_spec", {
        "battery_voltage": "battery_voltage", "max_pv_voltage": "max_pv_voltage",
        "max_charge_current": "max_charge_current", "efficiency": "efficiency",
    }),
    "cable": (CableSpecification, "cable_spec", {
        "cable_type": "cable_type", "size_mm": "size_mm", "ampacity": "ampacity", "voltage_rating": "voltage_rating",
    }),
    "fuse": (FuseSpecification, "fuse_spec", {
        "fuse_type": "fuse_type", "current_rating": "current_rating", "voltage_rating": "voltage_rating", "poles": "poles",
    }),
    "breaker": (BreakerSpecification, "breaker_spec", {
        "breaker_type": "breaker_type", "current_rating": "current_rating", "voltage_rating": "voltage_rating",
        "poles": "poles", "breaking_capacity": "breaking_capacity",
    }),
    "spd": (SPDSpecification, "spd_spec", {
        "spd_type": "spd_type", "voltage_rating": "voltage_rating", "protection_level": "protection_level",
    }),
    "isolator": (IsolatorSpecification, "isolator_spec", {
        "isolator_type": "isolator_type", "current_rating": "current_rating", "voltage_rating": "voltage_rating", "poles": "poles",
    }),
    "mounting_structure": (MountingStructureSpecification, "mounting_structure_spec", {
        "structure_type": "structure_type", "panel_capacity": "panel_capacity",
    }),
    "accessory": (AccessorySpecification, "accessory_spec", {
        "accessory_type": "accessory_type", "unit": "unit",
    }),
}

SPECIFICATION_COLUMNS = tuple(
    f"{kind}_{column}"
    for kind, (_, _, mapping) in SPECIFICATIONS.items()
    for column in mapping
)


class ProductListingResource(resources.ModelResource):
    """Import/export a product and its linked engineering specification."""

    vendor = fields.Field(column_name="vendor", attribute="vendor", widget=ForeignKeyWidget(Vendor, field="id"))
    categories = fields.Field(
        column_name="categories", attribute="categories",
        widget=ManyToManyWidget(Category, field="slug", separator="|"),
    )
    specification_type = fields.Field(column_name="specification_type", attribute=None, readonly=True)

    # These values are deliberately not ProductListing attributes. They remain
    # visible in CSV exports and are processed after the product is saved.
    for _column in SPECIFICATION_COLUMNS:
        locals()[_column] = fields.Field(column_name=_column, attribute=None)
    del _column

    class Meta:
        model = ProductListing
        fields = (
            "id", "name", "vendor", "categories", "manufacturer", "brand", "model_number",
            "country_of_origin", "supplier_price", "stock", "minimum_order_quantity", "weight",
            "description", "technical_specification", "warranty_period_months", "lead_time_days",
            "shipping_type", "fixed_shipping_fee", "requires_shipping", "requires_negotiation",
            "is_negotiable", "is_active", "is_featured", "is_new", "is_best_seller",
            "is_limited_stock", "is_fast_moving", "is_imported", "is_verified_supplier",
            "specification_type", *SPECIFICATION_COLUMNS,
        )
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
        use_bulk = False  # specs must follow their saved product row
        batch_size = 500

    def before_import_row(self, row, **kwargs):
        spec_type = str(row.get("specification_type") or "").strip().lower()
        if spec_type and spec_type not in SPECIFICATIONS:
            raise ValueError(f"Unknown specification_type '{spec_type}'. Use: {', '.join(SPECIFICATIONS)}.")

    def after_save_instance(self, instance, row, **kwargs):
        spec_type = str(row.get("specification_type") or "").strip().lower()
        if not spec_type:
            return

        spec_model, _related_name, column_map = SPECIFICATIONS[spec_type]
        values = {}
        for csv_field, model_field in column_map.items():
            value = row.get(f"{spec_type}_{csv_field}")
            if value not in (None, ""):
                values[model_field] = spec_model._meta.get_field(model_field).to_python(value)

        required_fields = [
            field.name for field in spec_model._meta.fields
            if not field.primary_key and field.name != "product" and not field.blank
            and not field.null and not field.has_default()
        ]
        missing_fields = [field_name for field_name in required_fields if field_name not in values]
        if missing_fields:
            raise ValueError(
                f"{spec_type} specification is missing required columns: {', '.join(missing_fields)}."
            )

        excluded_fields = [
            field.name for field in spec_model._meta.fields
            if field.name not in values and field.name not in {"id", "product"}
        ]

        try:
            specification = spec_model.objects.get(product=instance)
        except spec_model.DoesNotExist:
            specification = spec_model(product=instance, **values)
            specification.full_clean(exclude=excluded_fields)
            specification.save()
        else:
            if values:
                for field_name, value in values.items():
                    setattr(specification, field_name, value)
                specification.full_clean(exclude=excluded_fields)
                specification.save(update_fields=list(values))

    def export_field(self, field, obj, **kwargs):
        column = field.column_name
        if column == "specification_type":
            for kind, (_model, related_name, _mapping) in SPECIFICATIONS.items():
                if hasattr(obj, related_name):
                    return kind
            return ""

        for kind, (model, related_name, mapping) in SPECIFICATIONS.items():
            prefix = f"{kind}_"
            if column.startswith(prefix):
                try:
                    specification = getattr(obj, related_name)
                except model.DoesNotExist:
                    return ""
                field_name = mapping.get(column[len(prefix):])
                return getattr(specification, field_name, "") if field_name else ""
        return super().export_field(field, obj, **kwargs)
