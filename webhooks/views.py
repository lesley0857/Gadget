from django.shortcuts import render

# Create your views here.
import hmac, hashlib, json
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from payments.tasks import process_payment

@csrf_exempt
def paystack_webhook(request):

    if request.method != "POST":
        return HttpResponse(status=405)

    signature = request.headers.get(
        "x-paystack-signature",
        ""
    )
    if not settings.PAYSTACK_SECRET_KEY:
        return HttpResponse(status=503)

    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(),
        request.body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(
        signature,
        computed
    ):
        return HttpResponse(status=401)

    try:
        payload = json.loads(
            request.body
        )
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    if payload.get("event") == "charge.success" and payload.get("data"):
        process_payment.delay(payload["data"])

    return HttpResponse(status=200)

