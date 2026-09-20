from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from orders.models import Order, OrderItem
from catalog.models import ProductListing, Category, PricingRule
from accounts.models import Vendor
from pricing.services import (
    calculate_paystack_fee,
    calculate_paystack_gross_amount,
    calculate_paystack_net_amount,
    calculate_checkout_pricing,
    calculate_price,
)

User = get_user_model()


class PaystackPricingServiceTests(TestCase):
    """
    Unit tests for Paystack fee inversion and centralized pricing calculations.
    Rules:
    - 1.5% + ₦100 fixed fee
    - Fixed fee waived for transactions < ₦2,500
    - Fee capped at ₦2,000 max
    """

    def test_case_01_small_amount_under_waiver_threshold(self):
        # ₦1,000 transaction: fee fixed portion waived because gross < ₦2,500
        # G = 1000 / (1 - 0.015) = 1000 / 0.985 = 1015.2284... -> ₦1,015.23
        # Paystack fee on ₦1,015.23 = 1015.23 * 0.015 = 15.22845 -> ₦15.23
        # Net received = 1015.23 - 15.23 = ₦1,000.00
        net = Decimal("1000.00")
        gross = calculate_paystack_gross_amount(net)
        self.assertEqual(gross, Decimal("1015.23"))
        fee = calculate_paystack_fee(gross)
        self.assertEqual(fee, Decimal("15.23"))
        received_net = calculate_paystack_net_amount(gross)
        self.assertEqual(received_net, net)

    def test_case_02_standard_amount_10k(self):
        # ₦10,000 transaction: standard range
        # G = (10000 + 100) / 0.985 = 10100 / 0.985 = 10253.807... -> ₦10,253.81
        # Fee = 10253.81 * 0.015 + 100 = 153.80715 + 100 = 253.81
        # Net received = 10253.81 - 253.81 = ₦10,000.00
        net = Decimal("10000.00")
        gross = calculate_paystack_gross_amount(net)
        self.assertEqual(gross, Decimal("10253.81"))
        fee = calculate_paystack_fee(gross)
        self.assertEqual(fee, Decimal("253.81"))
        received_net = calculate_paystack_net_amount(gross)
        self.assertEqual(received_net, net)

    def test_case_03_standard_amount_100k(self):
        # ₦100,000 transaction: standard range (below cap)
        # G = (100000 + 100) / 0.985 = 100100 / 0.985 = 101624.365... -> ₦101,624.37
        # Fee = 101624.37 * 0.015 + 100 = 1524.36555 + 100 = 1624.37
        # Net received = 101624.37 - 1624.37 = ₦100,000.00
        net = Decimal("100000.00")
        gross = calculate_paystack_gross_amount(net)
        self.assertEqual(gross, Decimal("101624.37"))
        fee = calculate_paystack_fee(gross)
        self.assertEqual(fee, Decimal("1624.37"))
        received_net = calculate_paystack_net_amount(gross)
        self.assertEqual(received_net, net)

    def test_case_04_capped_amount_500k(self):
        # ₦500,000 transaction: fee hits the ₦2,000 cap
        # Gross = 500000 + 2000 = ₦502,000.00
        # Fee = min(502000 * 0.015 + 100, 2000) = ₦2,000.00
        # Net received = 502000.00 - 2000.00 = ₦500,000.00
        net = Decimal("500000.00")
        gross = calculate_paystack_gross_amount(net)
        self.assertEqual(gross, Decimal("502000.00"))
        fee = calculate_paystack_fee(gross)
        self.assertEqual(fee, Decimal("2000.00"))
        received_net = calculate_paystack_net_amount(gross)
        self.assertEqual(received_net, net)

    def test_case_05_large_capped_amount_1m(self):
        # ₦1,000,000 transaction: fee hits the ₦2,000 cap
        # Gross = 1000000 + 2000 = ₦1,002,000.00
        # Fee = min(1002000 * 0.015 + 100, 2000) = ₦2,000.00
        # Net received = 1002000.00 - 2000.00 = ₦1,000,000.00
        net = Decimal("1000000.00")
        gross = calculate_paystack_gross_amount(net)
        self.assertEqual(gross, Decimal("1002000.00"))
        fee = calculate_paystack_fee(gross)
        self.assertEqual(fee, Decimal("2000.00"))
        received_net = calculate_paystack_net_amount(gross)
        self.assertEqual(received_net, net)

    def test_case_06_with_shipping_fee(self):
        # Subtotal: ₦18,000.00, Shipping: ₦2,000.00 -> Total: ₦20,000.00
        pricing = calculate_checkout_pricing(
            subtotal=Decimal("18000.00"),
            shipping=Decimal("2000.00")
        )
        self.assertEqual(pricing.net_total, Decimal("20000.00"))
        self.assertEqual(pricing.total, Decimal("20000.00"))
        self.assertEqual(pricing.paystack_amount_kobo, 2000000)

    def test_case_07_with_vat_and_discount(self):
        # Subtotal: ₦50,000, Shipping: ₦3,000, VAT: ₦3,750, Discount: ₦5,000
        # Total = 50000 + 3000 + 3750 - 5000 = ₦51,750.00
        pricing = calculate_checkout_pricing(
            subtotal=Decimal("50000.00"),
            shipping=Decimal("3000.00"),
            vat=Decimal("3750.00"),
            discount=Decimal("5000.00")
        )
        self.assertEqual(pricing.net_total, Decimal("51750.00"))
        self.assertEqual(pricing.total, Decimal("51750.00"))
        self.assertEqual(pricing.paystack_amount_kobo, 5175000)

    def test_case_08_zero_amount(self):
        # Zero amount edge case
        pricing = calculate_checkout_pricing(subtotal=Decimal("0.00"))
        self.assertEqual(pricing.net_total, Decimal("0.00"))
        self.assertEqual(pricing.total, Decimal("0.00"))
        self.assertEqual(pricing.paystack_amount_kobo, 0)

    def test_case_09_negative_amount_safety(self):
        # Negative discount exceeding subtotal
        pricing = calculate_checkout_pricing(
            subtotal=Decimal("100.00"),
            discount=Decimal("200.00")
        )
        self.assertEqual(pricing.net_total, Decimal("0.00"))
        self.assertEqual(pricing.total, Decimal("0.00"))

    def test_case_10_kobo_exactness(self):
        # Ensure paystack_amount_kobo is always an integer with exact conversion
        pricing = calculate_checkout_pricing(subtotal=Decimal("12345.67"))
        self.assertIsInstance(pricing.paystack_amount_kobo, int)
        self.assertEqual(pricing.paystack_amount_kobo, int(pricing.total * 100))

    def test_case_11_threshold_boundary_edge(self):
        # Test exact boundary where waiver applies vs does not apply
        # Threshold: ₦2,500 gross
        # At gross = ₦2,499.00 -> fee = 2499 * 0.015 = ₦37.49 (waived fixed)
        fee_below = calculate_paystack_fee(Decimal("2499.00"))
        self.assertEqual(fee_below, Decimal("37.49"))

        # At gross = ₦2,500.00 -> fee = 2500 * 0.015 + 100 = 37.50 + 100 = ₦137.50
        fee_at = calculate_paystack_fee(Decimal("2500.00"))
        self.assertEqual(fee_at, Decimal("137.50"))

    def test_case_12_cap_boundary_edge(self):
        # Cap boundary: fee reaches ₦2,000 when G * 0.015 + 100 = 2000 => G = 1900 / 0.015 = ₦126,666.67
        # At G = 126,666.67 -> fee = min(126666.67 * 0.015 + 100, 2000) = min(2000.00, 2000) = ₦2,000.00
        fee_capped = calculate_paystack_fee(Decimal("126666.67"))
        self.assertEqual(fee_capped, Decimal("2000.00"))

    def test_case_13_as_dict_helper(self):
        pricing = calculate_checkout_pricing(subtotal=Decimal("5000.00"))
        d = pricing.as_dict()
        self.assertIn("amount_before_gateway_fee", d)
        self.assertIn("gateway_fee", d)
        self.assertIn("total", d)
        self.assertIn("paystack_amount_kobo", d)
        self.assertEqual(d["amount_before_gateway_fee"], Decimal("5000.00"))


class OrderModelAndIntegrationTests(TestCase):
    """Integration and audit trail tests."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="testpassword"
        )
        self.vendor_user = User.objects.create_user(
            username="testvendor",
            email="vendor@example.com",
            password="testpassword"
        )
        self.vendor = Vendor.objects.create(
            user=self.vendor_user,
            store_name="Solar Pro Store"
        )
        self.category = Category.objects.create(name="Solar Panels", slug="solar-panels")
        self.product = ProductListing.objects.create(
            vendor=self.vendor,
            name="Mono Solar Panel 400W",
            supplier_price=Decimal("45000.00"),
            weight=Decimal("18.5"),
            fixed_shipping_fee=Decimal("2500.00"),
            is_active=True
        )
        self.pricing_rule = PricingRule.objects.create(
            name="Solar 10% Markup",
            rule_type=PricingRule.MARKUP_PERCENTAGE,
            value=Decimal("10.00"),
            product=self.product,
            priority=10
        )

    def test_case_14_order_creation_stores_audit_breakdown(self):
        pricing = calculate_checkout_pricing(
            subtotal=Decimal("50000.00"),
            shipping=Decimal("2500.00")
        )

        order = Order.objects.create(
            customer=self.user,
            reference="TEST-REF-001",
            subtotal=pricing.subtotal,
            shipping_amount=pricing.shipping,
            shipping_fee=pricing.shipping,
            amount_before_gateway_fee=pricing.net_total,
            gateway_fee=pricing.gateway_fee,
            total_amount=pricing.total,
            status="processing",
            email=self.user.email,
        )

        self.assertEqual(order.subtotal, Decimal("50000.00"))
        self.assertEqual(order.shipping_amount, Decimal("2500.00"))
        self.assertEqual(order.total_amount, Decimal("52500.00"))
        self.assertIsNone(order.amount_paid)

    def test_case_15_order_paid_records_amount_paid(self):
        pricing = calculate_checkout_pricing(
            subtotal=Decimal("10000.00"),
            shipping=Decimal("1000.00")
        )

        order = Order.objects.create(
            customer=self.user,
            reference="TEST-REF-002",
            subtotal=pricing.subtotal,
            shipping_amount=pricing.shipping,
            shipping_fee=pricing.shipping,
            amount_before_gateway_fee=pricing.net_total,
            gateway_fee=pricing.gateway_fee,
            total_amount=pricing.total,
            status="processing",
            email=self.user.email,
        )

        # Simulate payment verification
        order.status = "paid"
        order.amount_paid = order.total_amount
        order.save()

        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertEqual(order.amount_paid, Decimal("11000.00"))
        self.assertEqual(order.total_amount, Decimal("11000.00"))

    def test_case_16_calculate_price_catalog_compatibility(self):
        price, margin = calculate_price(self.product)
        self.assertIsInstance(price, Decimal)
        self.assertIsInstance(margin, Decimal)
        # Cost 45000, 10% markup -> base = 49500.
        # With Paystack 1.5% + 100: (49500 + 100) / 0.985 = 50355.33
        self.assertEqual(price, Decimal("50355.33"))
        self.assertEqual(margin, Decimal("5355.33"))
