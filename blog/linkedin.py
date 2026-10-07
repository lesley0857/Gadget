import json
import logging
import urllib.error
import urllib.request
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import BlogPost

logger = logging.getLogger(__name__)


def publish_blog_post(post_id):
    """Publish a saved public blog post to the configured LinkedIn author."""
    with transaction.atomic():
        post = BlogPost.objects.select_for_update().filter(pk=post_id).first()
        if not post or not post.is_published or post.linkedin_post_id:
            return
        now = timezone.now()
        if post.linkedin_publish_started_at and post.linkedin_publish_started_at > now - timedelta(minutes=10):
            return
        post.linkedin_publish_started_at = now
        post.linkedin_publish_error = ""
        post.save(update_fields=["linkedin_publish_started_at", "linkedin_publish_error"])

    token = getattr(settings, "LINKEDIN_ACCESS_TOKEN", "")
    author = getattr(settings, "LINKEDIN_AUTHOR_URN", "")
    site_url = getattr(settings, "PUBLIC_SITE_URL", "")
    if not token or not author or not site_url:
        _record_failure(post_id, "Set LINKEDIN_ACCESS_TOKEN, LINKEDIN_AUTHOR_URN and PUBLIC_SITE_URL to enable LinkedIn publishing.")
        return

    article_url = site_url + reverse("blog_detail", args=[post.slug])
    prefix = f"{post.title}\n\n"
    link = f"\n\nRead more: {article_url}"
    excerpt = post.excerpt.strip()
    commentary = prefix + excerpt[:max(0, 2900 - len(prefix) - len(link))] + link
    payload = {
        "author": author,
        "commentary": commentary[:2900],
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    request = urllib.request.Request(
        "https://api.linkedin.com/rest/posts",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Linkedin-Version": getattr(settings, "LINKEDIN_API_VERSION", "202610"),
            "X-Restli-Protocol-Version": "2.0.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
            linkedin_post_id = response.headers.get("x-restli-id")
        if not linkedin_post_id:
            raise RuntimeError("LinkedIn returned success without an x-restli-id response header.")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as exc:
        detail = f"LinkedIn API returned HTTP {exc.code}." if isinstance(exc, urllib.error.HTTPError) else str(exc)
        logger.exception("LinkedIn publishing failed for blog post %s", post_id)
        _record_failure(post_id, detail[:1000])
        return

    BlogPost.objects.filter(pk=post_id, linkedin_post_id="").update(
        linkedin_post_id=linkedin_post_id,
        linkedin_url=f"https://www.linkedin.com/feed/update/{quote(linkedin_post_id, safe='')}/",
        linkedin_publish_error="",
        linkedin_publish_started_at=None,
    )


def _record_failure(post_id, message):
    BlogPost.objects.filter(pk=post_id, linkedin_post_id="").update(
        linkedin_publish_error=message,
        linkedin_publish_started_at=None,
    )
