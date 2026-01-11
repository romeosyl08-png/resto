from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .services import ReferralService, LoyaltyService


@receiver(post_save, sender=Order)
def on_order_paid(sender, instance: Order, created, **kwargs):
    # déclencher uniquement au passage PAID
    if instance.status == "PAID":
        ReferralService.try_qualify_and_reward(instance)
        LoyaltyService.on_order_paid(instance)
