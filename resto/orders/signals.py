from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import OrderItem, Order
from marketing.services import LoyaltyService


@receiver(post_save, sender=OrderItem)
def orderitem_saved(sender, instance, **kwargs):
    order = instance.order
    order.recompute_subtotal()
    order.save(update_fields=["subtotal", "total"])

@receiver(post_delete, sender=OrderItem)
def orderitem_deleted(sender, instance, **kwargs):
    order = instance.order
    order.recompute_subtotal()
    order.save(update_fields=["subtotal", "total"])



@receiver(pre_save, sender=Order)
def _order_pre_save(sender, instance: Order, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    prev = Order.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    instance._previous_status = prev

@receiver(post_save, sender=Order)
def _order_post_save(sender, instance: Order, created, **kwargs):
    prev = getattr(instance, "_previous_status", None)
    if prev != "delivered" and instance.status == "delivered":
        LoyaltyService.on_order_delivered(instance)
    elif prev == "delivered" and instance.status != "delivered":
        LoyaltyService.on_order_undelivered(instance)


@receiver(post_delete, sender=Order)
def _order_post_delete(sender, instance: Order, **kwargs):
    if instance.user and (instance.status == "delivered" or instance.loyalty_points_used):
        LoyaltyService.on_order_undelivered(instance, reset_referral_flag=False)
