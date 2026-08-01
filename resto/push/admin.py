# push/admin.py
from django.contrib import admin
from .models import ScheduledNotification, PushSubscription
from django.utils import timezone
from django.contrib import messages
from django.core.management import call_command

@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "browser_id", "endpoint", "created_at")
    search_fields = ("user__username", "browser_id")

@admin.register(ScheduledNotification)
class ScheduledNotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "send_at", "sent")
    list_filter = ("sent",)
    search_fields = ("title", "body")
    ordering = ("-send_at",)
    actions = ["send_now"]

    def send_now(self, request, queryset):
        """Bouton admin pour envoyer immédiatement la notif"""
        for notif in queryset:
            if not notif.sent:
                call_command("send_scheduled_notifications", notif_id=notif.id)
        messages.success(request, "Notifications envoyées immédiatement.")
    send_now.short_description = "Envoyer maintenant"
