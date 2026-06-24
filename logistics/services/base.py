class BaseLogisticsProvider:

    def get_rates(self, pickup, delivery):
        raise NotImplementedError

    def create_shipment(self, pickup, delivery, selected_option):
        raise NotImplementedError