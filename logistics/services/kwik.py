import requests
from django.conf import settings


class KwikProvider:

    BASE_URL = "https://api.kwik.delivery/v1"

    def __init__(self):
        self.token = getattr(settings, "KWIK_TOKEN", None)

    def get_quote(self, pickup, delivery, weight):
        """
        Returns normalized shipping options (NO Decimal inside)
        """

        if not self.token:
            print("❌ KWIK TOKEN NOT SET")
            return []

        payload = {
            "pickup_address": pickup.get("address"),
            "drop_address": delivery.get("address"),
            "pickup_lat": pickup.get("latitude"),
            "pickup_lng": pickup.get("longitude"),
            "drop_lat": delivery.get("latitude"),
            "drop_lng": delivery.get("longitude"),
            "weight": float(weight) if weight else 1.0
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            res = requests.post(
                f"{self.BASE_URL}/quote",
                json=payload,
                headers=headers,
                timeout=10
            )

            data = res.json()

            print("📦 KWIK RAW RESPONSE:", data)  # 🔥 DEBUG

        except Exception as e:
            print("❌ KWIK REQUEST FAILED:", e)
            return []

        # 🚨 Validate response
        if not data or "data" not in data:
            print("❌ INVALID KWIK RESPONSE")
            return []

        results = []

        for item in data.get("data", []):

            try:
                fee = float(item.get("amount", 0))  # ✅ ALWAYS FLOAT
            except:
                fee = 0.0

            # 🔥 Add your platform margin here
            margin_percent = 0.10  # 10%
            fee_with_margin = round(fee * (1 + margin_percent), 2)

            results.append({
                "id": str(item.get("service_id")),   # ALWAYS STRING
                "provider": "Kwik",
                "name": item.get("service_name", "Standard Delivery"),
                "fee": fee_with_margin,              # FLOAT ONLY
                "base_fee": fee,                     # FLOAT ONLY
                "eta": item.get("eta", "N/A")
            })

        return results