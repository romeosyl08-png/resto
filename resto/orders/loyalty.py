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

    meals_delivered = count_meals(order)
    if meals_delivered <= 0:
        return

    account.points += meals_delivered

    free_count = account.points // 8
    account.points = account.points % 8
    account.save(update_fields=["points"])

    for _ in range(free_count):
        FreeMealVoucher.objects.create(user=order.user)
