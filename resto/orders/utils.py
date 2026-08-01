from orders.models import Order
from django.db.models import Sum, Q
from decimal import Decimal


def build_cart_summary(cart):
    subtotal = cart.get_subtotal_price()
    discount = cart.get_discount_amount()
    total = cart.get_total_after_discount()
    return {
        "count": len(cart),
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "promo_code": cart.promo_code,
        "has_discount": discount > Decimal("0.00"),
    }


def meals_by_price(user):
    qs = (
        Order.objects
        .filter(user=user, status="delivered")
        .aggregate(
            c500=Sum("items__quantity", filter=Q(items__unit_price=500)),
            c1000=Sum("items__quantity", filter=Q(items__unit_price=1000)),
            c1500=Sum("items__quantity", filter=Q(items__unit_price=1500)),
        )
    )

    return {
        "c500": qs["c500"] or 0,
        "c1000": qs["c1000"] or 0,
        "c1500": qs["c1500"] or 0,
    }


