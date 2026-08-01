# push/services.py
import json
from pywebpush import webpush
from django.conf import settings

def send_push(sub, title, body):
    webpush(
        subscription_info={
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        },
        data=json.dumps({"title": title, "body": body}),
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": settings.VAPID_EMAIL}
    )
