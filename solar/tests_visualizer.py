"""
Unit and integration tests for the Three.js 3D Solar Equipment Visualizer.
Tests verification of quantities, model mapping, missing asset handling,
and view integration.
"""

import json
from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model

from catalog.models import Category, ProductListing
from accounts.models import Vendor
from solar.models import (
    SolarDesign,
    Product3DModel,
    PanelSpecification,
    BatterySpecification,
    InverterSpecification,
)
from solar.services.visualizer_service import build_visualizer_data
from solar.views import solar_design_result


User = get_user_model()


class Solar3DVisualizerTests(TestCase):
    """Test suite for the 3D Solar Equipment Visualizer."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpassword123",
        )
        self.vendor = Vendor.objects.create(
            user=self.user,
            store_name="Remarobe Test Store",
        )
        self.category = Category.objects.create(
            name="Solar Equipment",
            slug="solar-equipment",
        )

        # 1. Solar Panel Listing
        self.panel_product = ProductListing.objects.create(
            name="Jinko Solar 650W Monocrystalline Panel",
            vendor=self.vendor,
            brand="Jinko Solar",
            manufacturer="JinkoSolar Holding Co.",
            model_number="Tiger Pro 650W",
            supplier_price=Decimal("150000.00"),
            cached_price=Decimal("175000.00"),
            stock=50,
            is_active=True,
        )
        self.panel_product.categories.add(self.category)

        # 2. Battery Listing
        self.battery_product = ProductListing.objects.create(
            name="Deye 200Ah 48V Lithium Battery",
            vendor=self.vendor,
            brand="Deye",
            manufacturer="Deye Technology Group",
            model_number="SE-G5.1",
            supplier_price=Decimal("850000.00"),
            cached_price=Decimal("950000.00"),
            stock=20,
            is_active=True,
        )
        self.battery_product.categories.add(self.category)

        # 3. Inverter Listing
        self.inverter_product = ProductListing.objects.create(
            name="SolarTech 5kVA Hybrid Inverter",
            vendor=self.vendor,
            brand="SolarTech",
            manufacturer="SolarTech Industries",
            model_number="ST-HYB-5K",
            supplier_price=Decimal("400000.00"),
            cached_price=Decimal("450000.00"),
            stock=15,
            is_active=True,
        )
        self.inverter_product.categories.add(self.category)

    def test_exact_equipment_quantities_6_panels_2_batteries_1_inverter(self):
        """
        Verify that a system requiring 6 panels, 2 batteries, and 1 inverter
        produces exactly those quantities in the visualizer configuration.
        """
        design = SolarDesign(
            project_name="Residential Villa Solar",
            operating_mode="hybrid",
            panel_result={
                "success": True,
                "selected": {
                    "total_quantity": 6,
                    "series_count": 3,
                    "parallel_count": 2,
                    "installed_power_kw": 3.9,
                    "panel": {
                        "id": self.panel_product.id,
                        "brand": "Jinko Solar",
                        "model": "Tiger Pro 650W",
                        "power": 650,
                    },
                },
            },
            battery_result={
                "success": True,
                "selected": {
                    "total_quantity": 2,
                    "actual_bank_voltage": 48.0,
                    "usable_energy_kwh": 9.6,
                    "battery": {
                        "id": self.battery_product.id,
                        "brand": "Deye",
                        "name": "Deye 200Ah 48V Lithium Battery",
                        "capacity_ah": 200,
                        "voltage": 48.0,
                    },
                },
            },
            inverter_result={
                "success": True,
                "selected": {
                    "id": self.inverter_product.id,
                    "name": "SolarTech 5kVA Hybrid Inverter",
                    "brand": "SolarTech",
                    "model": "ST-HYB-5K",
                    "quantity": 1,
                    "rated_power": 5000,
                    "rated_power_kw": 5.0,
                    "phase": "single_phase",
                },
            },
            load_result={"daily_energy_kwh": 14.5},
            voltage_result={"nominal_voltage": 48.0},
        )

        data = build_visualizer_data(design)

        # Check Panels
        panels = data["equipment"]["panels"]
        self.assertEqual(panels["quantity"], 6)
        self.assertEqual(panels["brand"], "Jinko Solar")
        self.assertEqual(panels["model"], "Tiger Pro 650W")
        self.assertEqual(panels["rating"], "650 W")
        self.assertEqual(panels["total_power_kw"], 3.9)

        # Check Batteries
        batteries = data["equipment"]["batteries"]
        self.assertEqual(batteries["quantity"], 2)
        self.assertEqual(batteries["brand"], "Deye")
        self.assertEqual(batteries["rating"], "200 Ah")
        self.assertEqual(batteries["usable_energy_kwh"], 9.6)

        # Check Inverter
        inverter = data["equipment"]["inverter"]
        self.assertEqual(inverter["quantity"], 1)
        self.assertEqual(inverter["brand"], "SolarTech")
        self.assertEqual(inverter["rating"], "5 kVA")
        self.assertEqual(inverter["rated_power_kw"], 5.0)

        # Check System Summary
        summary = data["system_summary"]
        self.assertEqual(summary["total_panels"], 6)
        self.assertEqual(summary["total_batteries"], 2)
        self.assertEqual(summary["total_inverters"], 1)

    def test_dynamic_quantity_changes(self):
        """
        Verify that changing calculated quantities (e.g. 10 panels, 4 batteries, 2 inverters)
        dynamically updates the visualizer configuration.
        """
        design = SolarDesign(
            project_name="Commercial Office Solar",
            operating_mode="hybrid",
            panel_result={
                "success": True,
                "selected": {
                    "total_quantity": 10,
                    "series_count": 5,
                    "parallel_count": 2,
                    "installed_power_kw": 6.5,
                    "panel": {
                        "id": self.panel_product.id,
                        "brand": "Jinko Solar",
                        "model": "Tiger Pro 650W",
                        "power": 650,
                    },
                },
            },
            battery_result={
                "success": True,
                "selected": {
                    "total_quantity": 4,
                    "actual_bank_voltage": 48.0,
                    "usable_energy_kwh": 19.2,
                    "battery": {
                        "id": self.battery_product.id,
                        "brand": "Deye",
                        "capacity_ah": 200,
                        "voltage": 48.0,
                    },
                },
            },
            inverter_result={
                "success": True,
                "selected": {
                    "id": self.inverter_product.id,
                    "brand": "SolarTech",
                    "quantity": 2,
                    "parallel_units": 2,
                    "rated_power_kw": 10.0,
                    "rated_power": 10000,
                },
            },
        )

        data = build_visualizer_data(design)

        self.assertEqual(data["equipment"]["panels"]["quantity"], 10)
        self.assertEqual(data["equipment"]["batteries"]["quantity"], 4)
        self.assertEqual(data["equipment"]["inverter"]["quantity"], 2)
        self.assertEqual(data["system_summary"]["total_panels"], 10)
        self.assertEqual(data["system_summary"]["total_batteries"], 4)
        self.assertEqual(data["system_summary"]["total_inverters"], 2)

    def test_3d_asset_mapping_verified_and_placeholder(self):
        """
        Verify that products with verified 3D assets map properly, and
        products without 3D assets gracefully fall back to placeholder status.
        """
        # Create a verified 3D asset for Jinko panel
        Product3DModel.objects.create(
            product=self.panel_product,
            equipment_category="panel",
            asset_url="/static/models3d/jinko_650w.glb",
            width_m=Decimal("1.134"),
            height_m=Decimal("0.035"),
            depth_m=Decimal("2.278"),
            scale_factor=Decimal("1.0"),
            status="verified",
        )

        design = SolarDesign(
            project_name="Asset Mapping Test",
            panel_result={
                "selected": {
                    "total_quantity": 4,
                    "panel": {"id": self.panel_product.id, "power": 650},
                }
            },
            battery_result={
                "selected": {
                    "total_quantity": 1,
                    "battery": {"id": self.battery_product.id, "capacity_ah": 200},
                }
            },
        )

        data = build_visualizer_data(design)

        # Panel has verified model
        panel_asset = data["equipment"]["panels"]["asset"]
        self.assertTrue(panel_asset["has_exact_model"])
        self.assertEqual(panel_asset["status"], "verified")
        self.assertEqual(panel_asset["asset_url"], "/static/models3d/jinko_650w.glb")
        self.assertEqual(panel_asset["width_m"], 1.134)

        # Battery has NO 3D asset record -> procedural placeholder
        battery_asset = data["equipment"]["batteries"]["asset"]
        self.assertFalse(battery_asset["has_exact_model"])
        self.assertEqual(battery_asset["status"], "placeholder")
        self.assertEqual(battery_asset["asset_url"], "")

    def test_missing_and_corrupt_data_handled_gracefully(self):
        """
        Verify that an empty SolarDesign or corrupted results do not crash
        the visualizer data builder.
        """
        empty_design = SolarDesign(project_name="Empty Test")
        data = build_visualizer_data(empty_design)

        self.assertIsInstance(data, dict)
        self.assertEqual(data["equipment"]["panels"]["quantity"], 0)
        self.assertEqual(data["equipment"]["batteries"]["quantity"], 0)
        self.assertEqual(data["equipment"]["inverter"]["quantity"], 0)
        self.assertIsNone(data["equipment"]["controller"])

    def test_view_integration_and_template_rendering(self):
        """
        Verify that solar_design_result view passes visualizer_data and
        visualizer_json to context, and the 3D container is rendered in HTML.
        """
        design = SolarDesign.objects.create(
            user=self.user,
            project_name="Villa System",
            operating_mode="hybrid",
            panel_result={"selected": {"total_quantity": 8, "panel": {"id": self.panel_product.id, "power": 650}}},
            battery_result={"selected": {"total_quantity": 2, "battery": {"id": self.battery_product.id, "capacity_ah": 200}}},
            inverter_result={"selected": {"quantity": 1, "rated_power_kw": 5.0, "rated_power": 5000}},
            load_result={"daily_energy_kwh": 12.0},
            voltage_result={"nominal_voltage": 48.0},
        )

        rf = RequestFactory()
        url = reverse("design_result", kwargs={"customer_slug": "villa-system", "design_id": design.id})
        request = rf.get(url)
        request.user = self.user

        response = solar_design_result(request, customer_slug="villa-system", design_id=design.id)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn('id="solar-3d-visualiser"', content)
        self.assertIn('id="solar-3d-container"', content)
        self.assertIn('id="solar-3d-data"', content)
        self.assertIn("solar3d/visualizer", content)
        self.assertIn("solar3d", content)
