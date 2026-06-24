from decimal import Decimal
from .models import PricingRule

def calculate_price(product):
    rule = PricingRule.objects.filter(
        category=product.category
    ).order_by("priority").first()

    if not rule:
        return product.base_price, Decimal("0")

    if rule.pricing_type == PricingRule.PERCENTAGE:
        fee = product.base_price * (rule.value / Decimal("100"))
    else:
        fee = rule.value

    return product.base_price + fee, fee
