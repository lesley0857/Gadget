from decimal import Decimal
from logistics.models import ShippingOption

MARGIN_PERCENT = Decimal("0.15")
MIN_MARGIN = Decimal("500")


def calculate_shipping_options(weight):

    options = ShippingOption.objects.filter(is_active=True)

    results = []

    for opt in options:

        cost = opt.base_fee + (opt.per_kg_fee * weight)

        margin = cost * MARGIN_PERCENT

        if margin < MIN_MARGIN:
            margin = MIN_MARGIN

        final_price = cost + margin

        results.append({
            "id": opt.id,
            "name": opt.name,
            "provider": opt.provider.name,
            "fee": round(final_price, 2),
            "delivery": f"{opt.delivery_min_days}-{opt.delivery_max_days} days"
        })

    return results