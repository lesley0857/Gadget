import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BlogPost

logger = logging.getLogger(__name__)


@receiver(post_save, sender=BlogPost)
def queue_linkedin_publish(sender, instance, **kwargs):
    if not instance.is_published or instance.linkedin_post_id:
        return

    post_id = instance.pk

    def publish_after_commit():
        from .linkedin import publish_blog_post
        publish_blog_post(post_id)

    transaction.on_commit(publish_after_commit)
