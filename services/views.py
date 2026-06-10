from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import *

def services_page(request):
    services = Service.objects.filter(is_active=True)
    return render(request,"partials/services.html",{
            "services": services,
            })


def service_detail(request, slug):

    service = get_object_or_404(
        Service,
        slug=slug
    )
    related_services = Service.objects.filter(is_active=True).exclude(id=service.id)[:3]


    if request.method == "POST":

        ServiceRFQ.objects.create(

            service=service,

            name=request.POST.get("name"),

            email=request.POST.get("email"),

            phone=request.POST.get("phone"),

            company=request.POST.get("company"),

            message=request.POST.get("message"),

            document=request.FILES.get("document")
        )

        messages.success(
            request,
            "Your quotation request has been submitted successfully."
        )

        return redirect(
            "service_detail",
            slug=slug
        )

    context = {
        "service": service,
        "related_services":related_services,
    }

    return render(
        request,
        "service_detail.html",
        context
    )