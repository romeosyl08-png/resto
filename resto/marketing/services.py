from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from .models import Promotion, PromotionRedemption, LoyaltyAccount, FreeItemVoucher
from orders.models import Order, OrderItem


@dataclass(frozen=True)
class PromoResult:
    ok: bool
    reason: str = ""
    discount: Decimal = Decimal("0.00")
    code: str | None = None


class PromoService:
    @staticmethod
    def _segment_ok(user, promo: Promotion) -> bool:
        if promo.segment == Promotion.Segment.ALL:
            return True
        # simple: NEW = no delivered orders
        if promo.segment == Promotion.Segment.NEW:
            return not Order.objects.filter(user=user, status="delivered").exists()
        if promo.segment == Promotion.Segment.INACTIVE_30D:
            last = Order.objects.filter(user=user, status="delivered").order_by("-created_at").first()
            if not last:
                return True
            return (timezone.now() - last.created_at).days >= 30
        return False

    @staticmethod
    def estimate(user, subtotal: Decimal, promo_code: str) -> PromoResult:
        code = (promo_code or "").strip().upper()
        if not code:
            return PromoResult(False, "EMPTY_CODE")

        promo = Promotion.objects.filter(code=code).first()
        if not promo or not promo.is_valid_now():
            return PromoResult(False, "INVALID_OR_EXPIRED")

        if promo.segment != Promotion.Segment.ALL and not user:
            return PromoResult(False, "LOGIN_REQUIRED")

        if user and not PromoService._segment_ok(user, promo):
            return PromoResult(False, "NOT_ELIGIBLE")

        if promo.min_order_amount and subtotal < promo.min_order_amount:
            return PromoResult(False, "MIN_ORDER_NOT_MET")

        # limits (optional but real)
        if promo.usage_limit_total is not None:
            used_total = PromotionRedemption.objects.filter(promotion=promo, status="APPLIED").count()
            if used_total >= promo.usage_limit_total:
                return PromoResult(False, "PROMO_LIMIT_REACHED")

        if user and promo.usage_limit_per_user is not None:
            used_user = PromotionRedemption.objects.filter(promotion=promo, user=user, status="APPLIED").count()
            if used_user >= promo.usage_limit_per_user:
                return PromoResult(False, "USER_LIMIT_REACHED")

        discount = Decimal("0.00")
        if promo.promo_type == Promotion.PromoType.PERCENT:
            discount = (subtotal * promo.value / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            discount = promo.value

        if promo.max_discount_amount is not None:
            discount = min(discount, promo.max_discount_amount)

        discount = min(discount, subtotal)
        if discount <= 0:
            return PromoResult(False, "NO_DISCOUNT")

        return PromoResult(True, discount=discount, code=promo.code)

    @staticmethod
    @transaction.atomic
    def apply_to_order(user, order: Order, promo_code: str) -> PromoResult:
        res = PromoService.estimate(user, order.subtotal, promo_code)
        if not res.ok:
            return res

        promo = Promotion.objects.get(code=res.code)

        # non-cumul: cancel previous
        PromotionRedemption.objects.filter(order=order, status="APPLIED").update(status="CANCELLED")

        PromotionRedemption.objects.create(
            promotion=promo,
            user=user,
            order=order,
            discount_amount=res.discount,
        )

        order.promo_code = promo.code
        order.discount_total += res.discount
        order.total = max(Decimal("0.00"), order.subtotal - order.discount_total)
        order.save(update_fields=["promo_code", "discount_total", "total"])
        return res


class LoyaltyService:
    STAMPS_TARGET = 8
    VOUCHER_MAX_VALUE = Decimal("2000.00")
    VOUCHER_DAYS_VALID = 30

    @staticmethod
    def _meals_count(order: Order) -> int:
        return sum(OrderItem.objects.filter(order=order).values_list("quantity", flat=True))

    @staticmethod
    @transaction.atomic
    def on_order_delivered(order: Order) -> None:
        if not order.user:
            return
        if order.status != "delivered":
            return

        acc, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
        acc.stamps += max(0, int(LoyaltyService._meals_count(order)))

        free_count = acc.stamps // LoyaltyService.STAMPS_TARGET
        acc.stamps = acc.stamps % LoyaltyService.STAMPS_TARGET
        acc.save(update_fields=["stamps", "updated_at"])

        for _ in range(free_count):
            FreeItemVoucher.objects.create(
                user=order.user,
                max_item_value=LoyaltyService.VOUCHER_MAX_VALUE,
                expires_at=timezone.now() + timezone.timedelta(days=LoyaltyService.VOUCHER_DAYS_VALID),
            )

    @staticmethod
    @transaction.atomic
    def apply_best_voucher_to_order(user, order: Order) -> tuple[bool, str, Decimal]:
        """
        Applique 1 bon dispo (le plus proche d'expirer) :
        remise = min(prix unitaire le moins cher, max_item_value).
        """
        v = (FreeItemVoucher.objects.select_for_update()
             .filter(user=user, status=FreeItemVoucher.Status.AVAILABLE, expires_at__gt=timezone.now())
             .order_by("expires_at")
             .first())
        if not v:
            return False, "NO_VOUCHER", Decimal("0.00")

        items = list(OrderItem.objects.filter(order=order))
        if not items:
            return False, "EMPTY_ORDER", Decimal("0.00")

        cheapest_unit = min(i.unit_price for i in items)
        discount = min(cheapest_unit, v.max_item_value)

        order.discount_total += discount
        order.total = max(Decimal("0.00"), order.subtotal - order.discount_total)
        order.save(update_fields=["discount_total", "total"])

        v.status = FreeItemVoucher.Status.USED
        v.used_order = order
        v.save(update_fields=["status", "used_order"])
        return True, "OK", discount
