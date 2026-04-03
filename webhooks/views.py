from django.shortcuts import render

# Create your views here.
import hmac, hashlib, json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from payments.tasks import process_payment

@csrf_exempt
def paystack_webhook(request):
    signature = request.headers.get("x-paystack-signature")

    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request.body,
        hashlib.sha512
    ).hexdigest()

    if signature != computed:
        return HttpResponse(status=401)

    payload = json.loads(request.body)

    if payload["event"] == "charge.success":
        process_payment.delay(payload["data"])

    return HttpResponse(status=200)
