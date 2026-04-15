import math
from decimal import Decimal

class GIGLProvider:

    def haversine(self, lat1, lon1, lat2, lon2):
        # 🌍 distance in KM
        if None in [lat1, lon1, lat2, lon2]:
            return 10  # fallback distance

        R = 6371
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))

        dphi = math.radians(float(lat2) - float(lat1))
        dlambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_quote(self, pickup, delivery, weight):

        distance = self.haversine(
            pickup.get("latitude"),
            pickup.get("longitude"),
            delivery.get("latitude"),
            delivery.get("longitude")
        )

        weight = float(weight or 1)

        # 🚚 PRICING MODEL (SIMULATED GIGL)
        base_fee = 800
        per_km = 120
        per_kg = 250

        fee = base_fee + (distance * per_km) + (weight * per_kg)

        return [
            {
                "id": f"gigl_standard_{round(distance)}",
                "provider": "GIGL",
                "name": "Standard Delivery",
                "fee": round(fee, 2),
                "eta": "1-3 days"
            },
            {
                "id": f"gigl_express_{round(distance)}",
                "provider": "GIGL",
                "name": "Express Delivery",
                "fee": round(fee * 1.5, 2),
                "eta": "Same day / Next day"
            }
        ]