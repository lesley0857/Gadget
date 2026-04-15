from logistics.services.kwik import KwikProvider
from logistics.services.gigl import GIGLProvider

class LogisticsAggregator:

    def __init__(self):
        self.kwik = KwikProvider()
        self.gigl = GIGLProvider()

    def apply_margin(self, options):
        margin_rate = 0.10  # 🔥 10% profit

        for opt in options:
            base_fee = float(opt["fee"])
            opt["base_fee"] = base_fee
            opt["fee"] = round(base_fee * (1 + margin_rate), 2)

        return options

    def get_all_rates(self, pickup, delivery, weight):

        all_options = []

        # ✅ KWIK (real)
        try:
            kwik_rates = self.kwik.get_quote(pickup, delivery, weight)
            all_options.extend(kwik_rates)
        except Exception as e:
            print("Kwik failed:", e)

        # ✅ GIGL (simulated)
        try:
            gigl_rates = self.gigl.get_quote(pickup, delivery, weight)
            all_options.extend(gigl_rates)
        except Exception as e:
            print("GIGL failed:", e)

        # ✅ APPLY PROFIT MARGIN
        all_options = self.apply_margin(all_options)

        # ✅ SORT CHEAPEST FIRST
        all_options.sort(key=lambda x: x["fee"])

        return all_options