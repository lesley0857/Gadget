"""
pricing/services.py

Centralized pricing and payment calculation service for Remarobe.
Handles:
1. Product & Catalog price calculation.
2. Paystack transaction fee calculation and recovery inversion.
3. Order & Checkout totals aggregation using strict Decimal arithmetic.
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass
from typing import Optional
from django.conf import settings


def calculate_price(product):
    """Calculate product selling price and margin fee."""
    if hasattr(product, "final_price") and callable(product.final_price):
        final = product.final_price()
        base = getattr(product, "supplier_price", getattr(product, "base_price", final))
        fee = max(Decimal("0.00"), Decimal(str(final)) - Decimal(str(base)))
        return Decimal(str(final)), fee
    base_price = Decimal(str(getattr(product, "base_price", getattr(product, "supplier_price", "0.00"))))
    return base_price, Decimal("0.00")


def get_paystack_fee_config():
    """Retrieve Paystack transaction fee settings with fallbacks."""
    pct = getattr(settings, "PAYSTACK_PERCENTAGE_FEE", Decimal("0.015"))
    fixed = getattr(settings, "PAYSTACK_FIXED_FEE", Decimal("100.00"))
    cap = getattr(settings, "PAYSTACK_FEE_CAP", Decimal("2000.00"))
    threshold = getattr(settings, "PAYSTACK_FEE_WAIVER_THRESHOLD", Decimal("2500.00"))
    return {
        "percentage": Decimal(str(pct)),
        "fixed": Decimal(str(fixed)),
        "cap": Decimal(str(cap)) if cap else None,
        "waiver_threshold": Decimal(str(threshold)),
    }


def calculate_paystack_fee(gross_amount: Decimal) -> Decimal:
    """
    Calculate the Paystack transaction fee for a given gross transaction amount.
    Rule:
    - 1.5% of gross transaction amount
    - + ₦100 fixed fee (waived if gross_amount < ₦2,500)
    - Capped at ₦2,000 max (if cap configured)
    """
    if not isinstance(gross_amount, Decimal):
        gross_amount = Decimal(str(gross_amount or 0))

    if gross_amount <= Decimal("0.00"):
        return Decimal("0.00")

    cfg = get_paystack_fee_config()
    pct = cfg["percentage"]
    fixed = cfg["fixed"]
    cap = cfg["cap"]
    waiver_threshold = cfg["waiver_threshold"]

    fee = gross_amount * pct

    if gross_amount >= waiver_threshold:
        fee += fixed

    if cap is not None and fee > cap:
        fee = cap

    return fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_paystack_gross_amount(net_amount: Decimal) -> Decimal:
    """
    Calculate the gross payment amount required so that after Paystack deducts
    its transaction fee, the remaining net amount equals net_amount.

    Mathematical Inversion:
    1. For net < waiver_threshold * (1 - pct):
       G = N / (1 - pct)
    2. For standard range (fee below cap):
       G = (N + fixed) / (1 - pct)
    3. For fee at or above cap:
       G = N + cap
    """
    if not isinstance(net_amount, Decimal):
        net_amount = Decimal(str(net_amount or 0))

    if net_amount <= Decimal("0.00"):
        return Decimal("0.00")

    cfg = get_paystack_fee_config()
    pct = cfg["percentage"]
    fixed = cfg["fixed"]
    cap = cfg["cap"]
    waiver_threshold = cfg["waiver_threshold"]

    one_minus_pct = Decimal("1.00") - pct
    if one_minus_pct <= Decimal("0.00"):
        raise ValueError("Invalid Paystack percentage fee configuration")

    # Check waiver threshold boundary
    # If G < waiver_threshold, N < waiver_threshold * (1 - pct)
    net_waiver_boundary = waiver_threshold * one_minus_pct
    if net_amount < net_waiver_boundary:
        gross = net_amount / one_minus_pct
        return gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Standard formula candidate with fixed fee
    gross_candidate = (net_amount + fixed) / one_minus_pct
    fee_candidate = gross_candidate * pct + fixed

    # Check if fee hits the cap
    if cap is not None and fee_candidate >= cap:
        gross = net_amount + cap
    else:
        gross = gross_candidate

    return gross.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_paystack_net_amount(gross_amount: Decimal) -> Decimal:
    """Calculate the net amount received after Paystack fee is deducted."""
    if not isinstance(gross_amount, Decimal):
        gross_amount = Decimal(str(gross_amount or 0))

    fee = calculate_paystack_fee(gross_amount)
    net = gross_amount - fee
    return max(Decimal("0.00"), net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class CheckoutPricing:
    subtotal: Decimal
    shipping: Decimal
    vat: Decimal
    discount: Decimal
    net_total: Decimal  # Commercial order value before gateway recovery
    gateway_fee: Decimal  # Paystack fee recovered from customer
    total: Decimal  # Final payable gross amount (charged to customer)
    paystack_amount_kobo: int  # Amount sent to Paystack API (in kobo)

    def as_dict(self):
        return {
            "subtotal": self.subtotal,
            "shipping": self.shipping,
            "vat": self.vat,
            "discount": self.discount,
            "net_total": self.net_total,
            "amount_before_gateway_fee": self.net_total,
            "gateway_fee": self.gateway_fee,
            "paystack_fee_recovered": self.gateway_fee,
            "total": self.total,
            "amount_payable": self.total,
            "paystack_amount_kobo": self.paystack_amount_kobo,
        }


def calculate_checkout_pricing(
    subtotal: Decimal,
    shipping: Decimal = Decimal("0.00"),
    vat: Decimal = Decimal("0.00"),
    discount: Decimal = Decimal("0.00"),
) -> CheckoutPricing:
    """
    Centralized pricing calculation for checkout and payments.
    Follows order of calculation:
    1. Base Subtotal
    2. Shipping
    3. VAT
    4. Discounts
    5. Net Total (Order Value before gateway fee)
    6. Paystack Gross Amount & Recovered Gateway Fee
    """
    subtotal_dec = Decimal(str(subtotal or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    shipping_dec = Decimal(str(shipping or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat_dec = Decimal(str(vat or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    discount_dec = Decimal(str(discount or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total = max(Decimal("0.00"), (subtotal_dec + shipping_dec + vat_dec - discount_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    kobo_amount = int(total * 100)
    gateway_fee = calculate_paystack_fee(total)

    return CheckoutPricing(
        subtotal=subtotal_dec,
        shipping=shipping_dec,
        vat=vat_dec,
        discount=discount_dec,
        net_total=total,
        gateway_fee=gateway_fee,
        total=total,
        paystack_amount_kobo=kobo_amount,
    )
