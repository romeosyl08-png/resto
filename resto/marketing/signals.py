from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from orders.models import Order
from marketing.models import LoyaltyAccount

User = get_user_model()

@receiver(post_save, sender=User)
def create_loyalty(sender, instance, created, **kwargs):
    if created:
        LoyaltyAccount.objects.create(user=instance)

@receiver(post_save, sender=Order)
def recompute_loyalty_on_delivery(sender, instance, **kwargs):
    if instance.status == "delivered":
        loyalty, _ = LoyaltyAccount.objects.get_or_create(user=instance.user)
        loyalty.recompute()
