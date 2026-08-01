from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from comptes.models import UserProfile
from .models import Promotion, PromotionRedemption, LoyaltyAccount
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
    @staticmethod
    @transaction.atomic
    def on_order_delivered(order: Order) -> None:
        if not order.user or order.status != "delivered":
            return

        acc, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=order.user)
        acc.recompute()

                # ---------------- PARRAINAGE ----------------
        if order.counted_for_referral:
            return

        try:
            profile = order.user.userprofile
        except UserProfile.DoesNotExist:
            return

        sponsor = profile.referred_by
        if not sponsor:
            return

        delivered_count = (
            Order.objects
            .filter(
                user__userprofile__referred_by=sponsor,
                status="delivered",
                counted_for_referral=True
            )
            .count()
            + 1
        )

        if delivered_count in (3, 6):
            sponsor.free_meals += 1
            sponsor.save(update_fields=["free_meals"])

        order.counted_for_referral = True
        order.save(update_fields=["counted_for_referral"])


    @staticmethod
    @transaction.atomic
    def on_order_undelivered(order: Order, *, reset_referral_flag: bool = True) -> None:
        if not order.user:
            return

        acc, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=order.user)
        acc.recompute()

        # rollback parrainage (recalcul du nombre de repas gratuits)
        LoyaltyService._recompute_free_meals_for_sponsor(order)

        if reset_referral_flag and order.counted_for_referral:
            order.counted_for_referral = False
            order.save(update_fields=["counted_for_referral"])

    @staticmethod
    def _recompute_free_meals_for_sponsor(order: Order) -> None:
        try:
            profile = order.user.userprofile
        except UserProfile.DoesNotExist:
            return

        sponsor = profile.referred_by
        if not sponsor:
            return

        delivered_count = (
            Order.objects
            .filter(
                user__userprofile__referred_by=sponsor,
                status="delivered",
                counted_for_referral=True
            )
            .count()
        )

        target = 0
        if delivered_count >= 6:
            target = 2
        elif delivered_count >= 3:
            target = 1

        if sponsor.free_meals != target:
            sponsor.free_meals = target
            sponsor.save(update_fields=["free_meals"])

    @staticmethod
    @transaction.atomic
    def apply_best_reward_to_order(user, order: Order) -> tuple[bool, str, Decimal]:
        if not user:
            return False, "NO_USER", Decimal("0.00")

        if order.loyalty_points_used:
            return False, "ALREADY_APPLIED", Decimal("0.00")

        items = list(OrderItem.objects.filter(order=order))
        if not items:
            return False, "EMPTY_ORDER", Decimal("0.00")

        acc, _ = LoyaltyAccount.objects.select_for_update().get_or_create(user=user)
        points = int(acc.points or 0)

        reward = ""
        points_used = 0
        discount = Decimal("0.00")

        if points >= 10:
            reward = "discount_500"
            points_used = 10
            discount = Decimal("500")
        else:
            return False, "NOT_ENOUGH_POINTS", Decimal("0.00")

        remaining = max(Decimal("0.00"), order.subtotal - (order.discount_total or Decimal("0.00")))
        discount = min(discount, remaining)
        if discount <= 0:
            return False, "NO_DISCOUNT", Decimal("0.00")

        order.discount_total += discount
        order.total = max(Decimal("0.00"), order.subtotal - order.discount_total)
        order.loyalty_points_used = points_used
        order.loyalty_reward = reward
        order.loyalty_discount = discount
        order.save(update_fields=[
            "discount_total",
            "total",
            "loyalty_points_used",
            "loyalty_reward",
            "loyalty_discount",
        ])

        acc.points = max(0, points - points_used)
        acc.save(update_fields=["points", "updated_at"])
        return True, "OK", discount

    @staticmethod
    @transaction.atomic
    def apply_best_voucher_to_order(user, order: Order) -> tuple[bool, str, Decimal]:
        return LoyaltyService.apply_best_reward_to_order(user, order)

    
