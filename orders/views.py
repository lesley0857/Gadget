from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import OrderCreateSerializer

class CreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OrderCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response({"order_id": order.id})


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Order


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Order

@login_required
def user_orders_json(request):

    orders = Order.objects.filter(customer=request.user).prefetch_related("items")

    data = []

    for order in orders:
        for item in order.items.all():

            listing = item.product_listing   # ✅ FIX HERE

            # IMAGE
            image = ""
            if listing.media.exists():
                image = listing.media.first().file.url

            data.append({
                "id": item.id,
                "name": listing.product.name,   # ✅ FIX
                "status": order.status,
                "quantity": item.quantity,
                "price": float(item.escrow_amount),
                "image": image
            })

    return JsonResponse({
        "success": True,
        "orders": data
    })