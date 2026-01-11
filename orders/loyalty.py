from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from orders.models import Order
from marketing.models import LoyaltyAccount, FreeItemVoucher



def count_meals(order: Order) -> int:
    return sum(item.quantity for item in order.items.all())





@transaction.atomic
def apply_loyalty_on_delivery(order: Order):
    if not order.user:
        return

    acc, _ = LoyaltyAccount.objects.get_or_create(user=order.user)

    meals_delivered = sum(i.quantity for i in order.items.all())
    acc.stamps += max(0, int(meals_delivered))

    free_count = acc.stamps // 8
    acc.stamps = acc.stamps % 8
    acc.save(update_fields=["stamps", "updated_at"])

    for _ in range(free_count):
        FreeItemVoucher.objects.create(
            user=order.user,
            max_item_value=Decimal("2000.00"),  # ajuste si besoin
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )

