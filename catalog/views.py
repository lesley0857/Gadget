from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions
from .models import ProductListing
from .serializers import ProductSerializer

class ProductListView(generics.ListAPIView):
    queryset = ProductListing.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

class ProductCreateView(generics.CreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor)
