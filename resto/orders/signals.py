from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import OrderItem

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
