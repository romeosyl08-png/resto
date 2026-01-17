from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

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
    VOUCHER_DAYS_VALID = 30

    TIERS = (500, 1000, 1500)

    @staticmethod
    @transaction.atomic
    def on_order_delivered(order: Order) -> None:
        if not order.user or order.status != "delivered":
            return

        acc, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=order.user)

        items = OrderItem.objects.filter(order=order)

        # incrément compteurs par prix unitaire
        for it in items:
            q = int(it.quantity or 0)
            if q <= 0:
                continue
            if it.unit_price == 500:
                acc.count_500 += q
            elif it.unit_price == 1000:
                acc.count_1000 += q
            elif it.unit_price == 1500:
                acc.count_1500 += q

        # crée bons par tier, décrémente modulo 8
        def issue(tier: int, field: str):
            n = getattr(acc, field)
            free_count = n // LoyaltyService.STAMPS_TARGET
            setattr(acc, field, n % LoyaltyService.STAMPS_TARGET)
            for _ in range(free_count):
                FreeItemVoucher.objects.create(
                    user=order.user,
                    tier_value=tier,
                    expires_at=timezone.now() + timedelta(days=LoyaltyService.VOUCHER_DAYS_VALID),
                )

        issue(500, "count_500")
        issue(1000, "count_1000")
        issue(1500, "count_1500")

        acc.save(update_fields=["count_500", "count_1000", "count_1500", "updated_at"])

    @staticmethod
    @transaction.atomic
    def apply_best_voucher_to_order(user, order: Order) -> tuple[bool, str, Decimal]:
        items = list(OrderItem.objects.filter(order=order))
        if not items:
            return False, "EMPTY_ORDER", Decimal("0.00")

        # quels tiers sont présents dans cette commande ?
        present_prices = set(i.unit_price for i in items)

        # prend le bon qui expire le plus tôt MAIS applicable
        v = (FreeItemVoucher.objects.select_for_update()
            .filter(
                user=user,
                status=FreeItemVoucher.Status.AVAILABLE,
                expires_at__gt=timezone.now(),
                tier_value__in=present_prices,  # clé : match exact
            )
            .order_by("expires_at")
            .first())

        if not v:
            return False, "NO_MATCHING_VOUCHER", Decimal("0.00")

        discount = Decimal(str(v.tier_value))  # valeur fixe, pas un plafond global
        order.discount_total += discount
        order.total = max(Decimal("0.00"), order.subtotal - order.discount_total)
        order.save(update_fields=["discount_total", "total"])

        v.status = FreeItemVoucher.Status.USED
        v.used_order = order
        v.save(update_fields=["status", "used_order"])
        return True, "OK", discount

