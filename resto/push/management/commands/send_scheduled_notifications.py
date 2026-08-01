# push/management/commands/send_scheduled_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from push.models import ScheduledNotification, PushSubscription
from django.conf import settings
from pywebpush import webpush

class Command(BaseCommand):
    help = "Envoie les notifications programmées"

    def add_arguments(self, parser):
        parser.add_argument(
            "--notif_id", type=int, help="Envoyer uniquement cette notification"
        )

    def handle(self, *args, **options):
        notif_id = options.get("notif_id")
        now = timezone.now()

        if notif_id:
            notifications = ScheduledNotification.objects.filter(id=notif_id, sent=False)
        else:
            notifications = ScheduledNotification.objects.filter(send_at__lte=now, sent=False)

        for notif in notifications:
            subs = PushSubscription.objects.all()
            for sub in subs:
                try:
                    webpush(
                        subscription_info={
                            "endpoint": sub.endpoint,
                            "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                        },
                        data={"title": notif.title, "body": notif.body},
                        vapid_private_key=settings.VAPID_PRIVATE_KEY,
                        vapid_claims={"sub": "mailto:admin@restot.com"},
                    )
                except Exception:
                    continue  # ignore les endpoints morts

            notif.sent = True
            notif.sent_at = now
            notif.save()

        self.stdout.write("Notifications envoyées.")
