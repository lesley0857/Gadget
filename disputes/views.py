from django.shortcuts import render, redirect
from django.conf import settings
from django.core.mail import send_mail

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

        dispute = Dispute.objects.create(
            order_item=item,
            raised_by=request.user,
            reason=reason
        )
        recipients = [email for _, email in getattr(settings, "ADMINS", [])]
        if not recipients and getattr(settings, "ADMIN_EMAIL", ""):
            recipients = [settings.ADMIN_EMAIL]
        if not recipients and getattr(settings, "DEFAULT_FROM_EMAIL", ""):
            recipients = [settings.DEFAULT_FROM_EMAIL]
        if recipients:
            send_mail(
                subject=f"New customer dispute #{dispute.id}",
                message=f"{request.user} raised a dispute for order item #{item.id}.`nReason: {reason}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=recipients,
                fail_silently=True,
            )
        return redirect("orders_page")

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