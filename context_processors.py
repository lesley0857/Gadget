from remarobeprojects.models import Project
from testimonials.models import Testimonial


def website_content(request):

    return {

        "featured_projects":
            Project.objects.filter(
                featured=True
            )[:12],

        "featured_testimonials":
            Testimonial.objects.filter(
                featured=True
            )[:12]
    }