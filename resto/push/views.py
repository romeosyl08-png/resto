# push/views.py
import json, hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import PushSubscription

@csrf_exempt
def subscribe(request):
    data = json.loads(request.body)
    browser_id = hashlib.sha256(
        request.META.get("HTTP_USER_AGENT", "").encode()
    ).hexdigest()

    PushSubscription.objects.update_or_create(
        endpoint=data["endpoint"],
        defaults={
            "p256dh": data["keys"]["p256dh"],
            "auth": data["keys"]["auth"],
            "browser_id": browser_id,
            "user": request.user if request.user.is_authenticated else None
        }
    )
    return JsonResponse({"status": "ok"})
