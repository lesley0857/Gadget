from django.shortcuts import render, get_object_or_404

from .models import Project


def project_detail(request, slug):
    project = get_object_or_404(Project,slug=slug)
    related_projects = Project.objects.exclude(id=project.id)[:3]
    return render(request,"project_detail.html",
        {"project": project,
         "related_projects": related_projects}
    )