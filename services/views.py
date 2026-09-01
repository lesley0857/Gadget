from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import *

def services_page(request):
    services = Service.objects.filter(is_active=True)
    return render(request,"partials/services.html",{
            "services": services,
            })


SERVICE_EXPLANATIONS = {
    "solar": "We assess your appliances and operating hours, design the PV, battery, inverter and protection arrangement, supply suitable equipment, install, test and explain the system before handover.",
    "electrical": "We inspect the site, clarify the load and safety requirements, prepare a practical material schedule, install or repair the electrical system, then test and commission the work.",
    "earthing": "We review soil and electrical conditions, select electrodes, conductors and protection accessories, install an interconnected earth system and test the final resistance.",
    "industrial": "We support distribution, control, motors, panels and plant electrical work from site assessment through materials, installation, testing and handover.",
}


def _service_explanation(service):
    searchable = f"{service.title} {service.slug}".lower()
    for key, explanation in SERVICE_EXPLANATIONS.items():
        if key in searchable:
            return explanation
    return "We begin by understanding your site and technical requirement, then provide a clear scope, suitable materials, competent installation and testing before handover."

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
        "related_services": related_services,
        "service_explanation": _service_explanation(service),
    }

    return render(
        request,
        "service_detail.html",
        context
    )