# push/models.py
from django.db import models
from django.contrib.auth.models import User

class PushSubscription(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    browser_id = models.CharField(max_length=64, null=True, blank=True)
    endpoint = models.URLField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} ({self.browser_id})"

class ScheduledNotification(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    send_at = models.DateTimeField(help_text="Date et heure d’envoi")
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} ({self.send_at})"

    class Meta:
        ordering = ["send_at"]
