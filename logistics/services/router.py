from logistics.models import Hub

def get_central_hub():
    return Hub.objects.filter(city="Lagos").first()


def route_order(vendor, customer_city):

    vendor_hub = vendor.hub
    central_hub = get_central_hub()

    if not vendor_hub or not central_hub:
        raise Exception("Missing hub configuration")

    # CASE 1: same city → direct
    if vendor_hub.city == customer_city:
        return {
            "type": "direct",
            "vendor_hub": vendor_hub,
            "central_hub": None
        }

    # CASE 2: vendor already at central hub
    if vendor_hub.id == central_hub.id:
        return {
            "type": "hub_to_customer",
            "vendor_hub": vendor_hub,
            "central_hub": central_hub
        }

    # CASE 3: multi hub
    return {
        "type": "multi_hub",
        "vendor_hub": vendor_hub,
        "central_hub": central_hub
    }