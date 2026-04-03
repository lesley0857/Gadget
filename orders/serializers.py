from rest_framework import serializers
from .models import Order, OrderItem
from catalog.models import Product
from pricing.services import calculate_price

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"

class OrderCreateSerializer(serializers.Serializer):
    items = serializers.ListField()

    def create(self, validated_data):
        user = self.context["request"].user
        order = Order.objects.create(customer=user, total_amount=0)

        total = 0
        for item in validated_data["items"]:
            product = Product.objects.get(id=item["product_id"])
            price, commission = calculate_price(product)

            OrderItem.objects.create(
                order=order,
                product=product,
                vendor=product.vendor,
                quantity=item["qty"],
                escrow_amount=price,
                commission=commission,
            )
            total += price * item["qty"]

        order.total_amount = total
        order.save()
        return order
