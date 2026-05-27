from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions
from .models import *
from .serializers import ProductSerializer
from django.db.models import Q
from catalog.models import ProductListing
from django.http import JsonResponse


def search_products(request):
    query = request.GET.get("q")

    products = ProductListing.objects.filter(
        Q(product__name__icontains=query) |
        Q(description__icontains=query)
    )

    return render(request, "catalogSearchResults.html", {
        "products": products,
        "query": query
    })

def search_suggestions(request):
    query = request.GET.get("q", "")

    if not query:
        return JsonResponse({"results": []})

    products = ProductListing.objects.filter(
        Q(product__name__icontains=query) |
        Q(description__icontains=query)|
        Q(product__category__name__icontains=query)

    ).select_related("product").prefetch_related("media")[:8] # limit results

    results = []

    for p in products:

        # 🔥 GET PRIMARY IMAGE
        media = p.media.filter(is_primary=True).first()

        # fallback to any image
        if not media:
            media = p.media.first()

    image_url = media.file.url if media and media.file else ""

    results.append({
        "id": p.id,
        "name": p.product.name,
        "image": image_url,
    })

    return JsonResponse({"results": results})

def category_products(request, name):

    category = Category.objects.get(name=name)

    products = ProductListing.objects.filter(
        categories__name=name,
        is_active=True
    ).distinct()
    categories = Category.objects.all()
    return render(request, "category.html", {
        "category": category,
        "categories":categories,
        "products": products
    })

class ProductListView(generics.ListAPIView):
    queryset = ProductListing.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

class ProductCreateView(generics.CreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(vendor=self.request.user.vendor)
