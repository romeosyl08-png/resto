from django.db import transaction
from .models import FreeMealVoucher, Order
from marketing.models import LoyaltyAccount # adapte si besoin


def count_meals(order: Order) -> int:
    return sum(item.quantity for item in order.items.all())


@transaction.atomic
def apply_loyalty_on_delivery(order: Order):
    if not order.user:
        return  # commandes invité = pas de fidélité

    account, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
    
    meals_delivered = sum(i.quantity for i in order.items.all())
    account.stamps += meals_delivered
    
    free_count = account.stamps // 8
    account.stamps = account.stamps % 8
    account.save(update_fields=["stamps"])
    
    for _ in range(free_count):
        FreeItemVoucher.objects.create(user=order.user)

