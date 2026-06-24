from django.shortcuts import render, get_object_or_404
from .models import BlogPost


def blog_detail(request, slug):

    blog = get_object_or_404(
        BlogPost,
        slug=slug,
        is_published=True
    )

    related_blogs = BlogPost.objects.filter(
        category=blog.category,
        is_published=True
    ).exclude(
        id=blog.id
    )[:5]

    latest_posts = BlogPost.objects.filter(
        is_published=True
    ).exclude(
        id=blog.id
    )[:6]

    context = {
        "blog": blog,
        "related_blogs": related_blogs,
        "latest_posts": latest_posts,
    }

    return render(
        request,
        "blog_detail.html",
        context
    )