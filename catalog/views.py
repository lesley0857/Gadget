from django.shortcuts import render

# Create your views here.
from rest_framework import generics, permissions
from .models import *
from .serializers import ProductSerializer
from django.db.models import Q
from catalog.models import ProductListing
from django.http import JsonResponse

def search_products(request):

    query = request.GET.get("q", "").strip()

    products = ProductListing.objects.filter(

        Q(name__icontains=query) |
        Q(description__icontains=query) |
        Q(categories__name__icontains=query)|
        Q(brand__icontains=query) |
        Q(manufacturer__icontains=query),

        is_active=True

    ).distinct()

    return render(
        request,
        "catalogSearchResults.html",
        {
            "products": products,
            "query": query,
        }
    )

def search_suggestions(request):

    query = request.GET.get("q","").strip()

    if len(query) < 2:
        return JsonResponse({})

    products = (
        ProductListing.objects
        .filter(
            Q(name__icontains=query) |
            Q(description__icontains=query),
            is_active=True
        )
        .prefetch_related(
            "media"
        )[:5]
    )

    categories = (
        Category.objects
        .filter(
            name__icontains=query
        )[:5]
    )

    brands = (
        ProductListing.objects
        .filter(
            brand__icontains=query
        )
        .values_list(
            "brand",
            flat=True
        )
        .distinct()[:5]
    )

    product_results = []

    for p in products:

        media = (
            p.media
            .filter(is_primary=True)
            .first()
        )

        if not media:
            media = p.media.first()

        product_results.append({

            "type":"product",

            "name":
                p.name,

            "image":
                media.file.url
                if media and media.file
                else "/static/images/product-placeholder.png",

            "price":
                str(p.final_price()),

            "url":
                f"/product/{p.name}/",
        })

    category_results = []

    for c in categories:

        category_results.append({

            "type":"category",

            "name":
                c.name,

            # category image
            "image":
                c.image.url
                if hasattr(c,"image")
                and c.image
                else "/static/images/category.png",

            "url":
                f"/category/{c.name}/",
        })

    brand_results = []

    for brand in brands:

        brand_results.append({

            "type":"brand",

            "name":
                brand,

            "image":
                "/static/images/brand.png",

            "url":
                f"/search/?q={brand}",
        })

    return JsonResponse({

        "products":
            product_results,

        "categories":
            category_results,

        "brands":
            brand_results,
    })


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
