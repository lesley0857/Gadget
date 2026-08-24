# solar/management/commands/migrate_products_to_marketplace.py
#
# One-time data migration: copies every row from the legacy
# solar catalog models (Battery, SolarPanel, Inverter,
# ChargeController, Cable, Fuse, Breaker, SPD, Isolator,
# MountingStructure, Accessory) into a ProductListing +
# matching Specification pair.
#
# USAGE
# -----
#   python manage.py migrate_products_to_marketplace --vendor-id 1 --dry-run
#   python manage.py migrate_products_to_marketplace --vendor-id 1
#
# --vendor-id is required. Every migrated listing needs a vendor
# (ProductListing.vendor is NOT NULL). Use whichever accounts.Vendor
# row represents "your own" catalog/warehouse if these aren't
# third-party listings.
#
# --category-id is optional. If given, every migrated listing is
# attached to that Category (e.g. a "Solar Equipment" category).
# ProductListing.categories is a ManyToMany, so you can also leave
# this off and assign categories later in bulk via the admin.
#
# Run with --dry-run first. It prints exactly what would be created
# without touching the database.
#
# SAFE TO RE-RUN: rows already migrated (matched by brand + model
# stored in ProductListing.brand / model_number) are skipped, so
# re-running after fixing an error won't create duplicates.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Copy legacy solar catalog rows (Battery, SolarPanel, "
        "Inverter, ChargeController, Cable, Fuse, Breaker, SPD, "
        "Isolator, MountingStructure, Accessory) into ProductListing "
        "+ Specification pairs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--vendor-id",
            type=int,
            required=True,
            help="accounts.Vendor id to assign as vendor on every migrated listing.",
        )
        parser.add_argument(
            "--category-id",
            type=int,
            default=None,
            help="Optional marketplace Category id to attach to every migrated listing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without writing to the database.",
        )

    def handle(self, *args, **options):
        from accounts.models import Vendor
        from solar.models import (
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
            BatterySpecification,
            PanelSpecification,
            InverterSpecification,
            ControllerSpecification,
            CableSpecification,
            FuseSpecification,
            BreakerSpecification,
            SPDSpecification,
            IsolatorSpecification,
            MountingStructureSpecification,
            AccessorySpecification,
        )

        try:
            from catalog.models import ProductListing, Category
        except ImportError as exc:
            raise CommandError(
                "Could not import ProductListing/Category from "
                "'marketplace.models'. If your app label isn't "
                "'marketplace', edit the import at the top of "
                "migrate_products_to_marketplace.py to match it."
            ) from exc

        dry_run = options["dry_run"]

        try:
            vendor = Vendor.objects.get(pk=options["vendor_id"])
        except Vendor.DoesNotExist:
            raise CommandError(f"No Vendor with id={options['vendor_id']}")

        category = None
        if options["category_id"] is not None:
            try:
                category = Category.objects.get(pk=options["category_id"])
            except Category.DoesNotExist:
                raise CommandError(f"No Category with id={options['category_id']}")

        plan = [
            ("Battery", Battery, BatterySpecification, self._battery_fields),
            ("SolarPanel", SolarPanel, PanelSpecification, self._panel_fields),
            ("Inverter", Inverter, InverterSpecification, self._inverter_fields),
            ("ChargeController", ChargeController, ControllerSpecification, self._controller_fields),
            ("Cable", Cable, CableSpecification, self._cable_fields),
            ("Fuse", Fuse, FuseSpecification, self._fuse_fields),
            ("Breaker", Breaker, BreakerSpecification, self._breaker_fields),
            ("SPD", SPD, SPDSpecification, self._spd_fields),
            ("Isolator", Isolator, IsolatorSpecification, self._isolator_fields),
            ("MountingStructure", MountingStructure, MountingStructureSpecification, self._mounting_fields),
            ("Accessory", Accessory, AccessorySpecification, self._accessory_fields),
        ]

        total_created = 0
        total_skipped = 0

        for label, legacy_model, spec_model, field_mapper in plan:
            created, skipped = self._migrate_one(
                label=label,
                legacy_model=legacy_model,
                spec_model=spec_model,
                field_mapper=field_mapper,
                vendor=vendor,
                category=category,
                ProductListing=ProductListing,
                dry_run=dry_run,
            )
            total_created += created
            total_skipped += skipped

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {total_created} ProductListing(s) "
                f"{'would be ' if dry_run else ''}created, "
                f"{total_skipped} skipped (already migrated)."
            )
        )

    # ------------------------------------------------------------
    # PER-MODEL MIGRATION
    # ------------------------------------------------------------

    def _migrate_one(
        self,
        *,
        label,
        legacy_model,
        spec_model,
        field_mapper,
        vendor,
        category,
        ProductListing,
        dry_run,
    ):
        rows = legacy_model.objects.all()
        created = 0
        skipped = 0

        self.stdout.write(f"\n--- {label} ({rows.count()} rows) ---")

        for row in rows:
            brand, model_number, name, description, price, active, spec_fields = field_mapper(row)

            already_exists = ProductListing.objects.filter(
                brand=brand,
                model_number=model_number,
            ).exists()

            if already_exists:
                skipped += 1
                continue

            self.stdout.write(f"  + {name} (brand={brand!r}, model={model_number!r}, price={price})")

            if dry_run:
                created += 1
                continue

            with transaction.atomic():
                listing = ProductListing.objects.create(
                    name=name,
                    vendor=vendor,
                    brand=brand,
                    model_number=model_number,
                    supplier_price=price,
                    description=description or name,
                    is_active=active,
                )

                if category is not None:
                    listing.categories.add(category)

                spec_model.objects.create(product=listing, **spec_fields)

            created += 1

        return created, skipped

    # ------------------------------------------------------------
    # FIELD MAPPERS
    #
    # Each returns:
    #   (brand, model_number, name, description, price, active, spec_field_dict)
    # ------------------------------------------------------------

    def _battery_fields(self, row):
        name = f"{row.brand} {row.model} {row.voltage}V {row.capacity_ah}Ah"
        spec = dict(
            battery_type=row.battery_type,
            voltage=row.voltage,
            capacity_ah=row.capacity_ah,
            depth_of_discharge=row.depth_of_discharge,
            efficiency=row.efficiency,
            max_discharge_current=row.max_discharge_current,
            max_charge_current=row.max_charge_current,
            cycles=row.cycles,
            warranty_years=row.warranty_years,
            weight=row.weight,
        )
        return row.brand, row.model, name, "", row.price, row.active, spec

    def _panel_fields(self, row):
        name = f"{row.brand} {row.model} {row.power}W"
        spec = dict(
            power=row.power,
            vmp=row.vmp,
            voc=row.voc,
            imp=row.imp,
            isc=row.isc,
            efficiency=row.efficiency,
        )
        return row.brand, row.model, name, "", row.price, row.active, spec

    def _inverter_fields(self, row):
        name = f"{row.brand} {row.model} {row.rated_power}W"
        spec = dict(
            rated_power=row.rated_power,
            surge_power=row.surge_power,
            dc_voltage=row.dc_voltage,
            output_voltage=row.output_voltage,
            frequency=row.frequency,
            phase=row.phase,
            efficiency=row.efficiency,
            hybrid=row.hybrid,
        )
        return row.brand, row.model, name, "", row.price, row.active, spec

    def _controller_fields(self, row):
        name = f"{row.brand} {row.model} {row.max_charge_current}A"
        spec = dict(
            battery_voltage=row.battery_voltage,
            max_pv_voltage=row.max_pv_voltage,
            max_charge_current=row.max_charge_current,
            efficiency=row.efficiency,
        )
        return row.brand, row.model, name, "", row.price, row.active, spec

    def _cable_fields(self, row):
        brand = row.manufacturer or ""
        model_number = row.name
        name = f"{row.name} {row.size_mm}mm\u00b2"
        spec = dict(
            cable_type=row.cable_type,
            size_mm=row.size_mm,
            ampacity=row.ampacity,
            voltage_rating=row.voltage_rating,
        )
        return brand, model_number, name, "", row.price_per_meter, row.active, spec

    def _fuse_fields(self, row):
        brand = row.manufacturer or ""
        model_number = row.name
        name = f"{row.name} {row.current_rating}A"
        spec = dict(
            fuse_type=row.fuse_type,
            current_rating=row.current_rating,
            voltage_rating=row.voltage_rating,
            poles=row.poles,
        )
        return brand, model_number, name, "", row.price, row.active, spec

    def _breaker_fields(self, row):
        brand = row.manufacturer or ""
        model_number = row.name
        name = f"{row.name} {row.current_rating}A"
        spec = dict(
            breaker_type=row.breaker_type,
            current_rating=row.current_rating,
            voltage_rating=row.voltage_rating,
            poles=row.poles,
            breaking_capacity=row.breaking_capacity,
        )
        return brand, model_number, name, "", row.price, row.active, spec

    def _spd_fields(self, row):
        brand = row.manufacturer or ""
        model_number = row.name
        name = f"{row.name} {row.voltage_rating}V"
        spec = dict(
            spd_type=row.spd_type,
            voltage_rating=row.voltage_rating,
            protection_level=row.protection_level,
        )
        return brand, model_number, name, "", row.price, row.active, spec

    def _isolator_fields(self, row):
        brand = row.manufacturer or ""
        model_number = row.name
        name = f"{row.name} {row.current_rating}A"
        spec = dict(
            isolator_type=row.isolator_type,
            current_rating=row.current_rating,
            voltage_rating=row.voltage_rating,
            poles=row.poles,
        )
        return brand, model_number, name, "", row.price, row.active, spec

    def _mounting_fields(self, row):
        brand = ""
        model_number = row.name
        name = row.name
        spec = dict(
            structure_type=row.structure_type,
            panel_capacity=row.panel_capacity,
        )
        return brand, model_number, name, "", row.price, row.active, spec

    def _accessory_fields(self, row):
        brand = ""
        model_number = row.name
        name = row.name
        spec = dict(
            accessory_type=row.accessory_type,
            unit=row.unit,
        )
        return brand, model_number, name, row.description or "", row.price, row.active, spec