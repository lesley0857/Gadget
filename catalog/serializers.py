from rest_framework import serializers
from .models import Category, ProductListing
from pricing.services import calculate_price

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = "__all__"

class ProductSerializer(serializers.ModelSerializer):
    final_price = serializers.SerializerMethodField()

    class Meta:
        model = ProductListing
        fields = "__all__"

    def get_final_price(self, obj):
        price, _ = calculate_price(obj)
        return price
