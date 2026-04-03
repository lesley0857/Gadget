from django.shortcuts import render, redirect

# Create your views here.
from rest_framework import generics
from django.contrib.auth.decorators import login_required
from .models import *
from .serializers import DisputeSerializer
from .models import *

class CreateDisputeView(generics.CreateAPIView):
    serializer_class = DisputeSerializer

@login_required
def dispute_page(request, item_id):
    item = OrderItem.objects.get(id=item_id)

    if request.method == "POST":
        reason = request.POST.get("reason")

        Dispute.objects.create(
            order_item=item,
            customer=request.user,
            reason=reason
        )

        return redirect("orders")

    return render(request, "dispute.html", {"item": item})

def create_dispute(request, item_id):
    item = OrderItem.objects.get(id=item_id)

    Dispute.objects.create(
        order_item=item,
        customer=request.user,
        reason=request.POST.get("reason")
    )

    return redirect("orders")

def resolve_dispute(request, dispute_id):
    dispute = Dispute.objects.get(id=dispute_id)

    dispute.resolved = True
    dispute.save()

    return redirect("admin_dashboard")