from django.core.management.base import BaseCommand
from django.utils import timezone

from cart.models import NegotiationRequest

class Command(BaseCommand):

    def handle(self,*args,**kwargs):

        NegotiationRequest.objects.filter(

            status="quoted",

            payment_link_expires_at__lt=
            timezone.now()

        ).update(

            status="expired"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Expired quotations updated."
            )
        )

