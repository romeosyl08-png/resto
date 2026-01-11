from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from .models import (
    Promotion, PromotionRedemption,
    ReferralCode, Referral, RewardLedger,
    LoyaltyAccount, FreeItemVoucher
)
from orders.models import Order, OrderItem  # adapte si ton app s'appelle différemment


@dataclass(frozen=True)
class PromoResult:
    ok: bool
    reason: str = ""
    discount: Decimal = Decimal("0.00")


class PromoService:
    @staticmethod
    def _user_segment_ok(user, promo: Promotion) -> bool:
        if promo.segment == Promotion.Segment.ALL:
            return True

        # NEW: no paid orders
        if promo.segment == Promotion.Segment.NEW:
            return not Order.objects.filter(user=user, status="PAID").exists()

        # INACTIVE_30D: last paid order older than 30 days
        if promo.segment == Promotion.Segment.INACTIVE_30D:
            last = Order.objects.filter(user=user, status="PAID").order_by("-paid_at").first()
            if not last or not last.paid_at:
                return True
            return (timezone.now() - last.paid_at).days >= 30

        return False

    @staticmethod
    def estimate_discount(user, order: Order, promo: Promotion) -> PromoResult:
        if not promo.is_currently_valid():
            return PromoResult(False, "PROMO_INACTIVE")

        if not PromoService._user_segment_ok(user, promo):
            return PromoResult(False, "NOT_ELIGIBLE")

        if promo.min_order_amount and order.total_amount < promo.min_order_amount:
            return PromoResult(False, "MIN_ORDER_NOT_MET")

        # usage limits
        if promo.usage_limit_total is not None:
            used_total = PromotionRedemption.objects.filter(promotion=promo, status="APPLIED").count()
            if used_total >= promo.usage_limit_total:
                return PromoResult(False, "PROMO_LIMIT_REACHED")

        if promo.usage_limit_per_user is not None:
            used_user = PromotionRedemption.objects.filter(promotion=promo, user=user, status="APPLIED").count()
            if used_user >= promo.usage_limit_per_user:
                return PromoResult(False, "USER_LIMIT_REACHED")

        discount = Decimal("0.00")
        if promo.promo_type == Promotion.PromoType.PERCENT:
            discount = (order.total_amount * promo.value / Decimal("100")).quantize(Decimal("0.01"))
        elif promo.promo_type == Promotion.PromoType.FIXED_AMOUNT:
            discount = promo.value
        elif promo.promo_type == Promotion.PromoType.FREE_ITEM:
            # handled via voucher/loyalty typically; keep discount 0 here
            discount = Decimal("0.00")

        if promo.max_discount_amount is not None:
            discount = min(discount, promo.max_discount_amount)

        discount = min(discount, order.total_amount)
        return PromoResult(True, discount=discount)

    @staticmethod
    @transaction.atomic
    def apply_promo(user, order: Order, promo_code: str, device_id: str | None = None, ip_hash: str | None = None) -> PromoResult:
        promo = Promotion.objects.filter(code=promo_code.strip().upper()).first()
        if not promo:
            return PromoResult(False, "PROMO_NOT_FOUND")

        res = PromoService.estimate_discount(user, order, promo)
        if not res.ok:
            return res

        # ensure 1 promo per order (non-cumul)
        PromotionRedemption.objects.filter(order=order, status="APPLIED").update(status="CANCELLED")

        PromotionRedemption.objects.create(
            promotion=promo,
            user=user,
            order=order,
            discount_amount=res.discount,
            device_id=device_id,
            ip_hash=ip_hash,
        )

        # apply to order (you may prefer separate fields)
        order.promo_code = promo.code
        order.discount_amount = res.discount
        order.total_amount = max(Decimal("0.00"), (order.subtotal_amount - res.discount))
        order.save(update_fields=["promo_code", "discount_amount", "total_amount"])

        return res


class ReferralService:
    REFERRAL_REWARD = Decimal("1000.00")  # ajuste
    REFERRAL_MIN_ORDER = Decimal("5000.00")  # ajuste

    @staticmethod
    def get_or_create_code(user) -> ReferralCode:
        obj, _ = ReferralCode.objects.get_or_create(
            user=user,
            defaults={"code": f"REF-{user.id:06d}"},
        )
        return obj

    @staticmethod
    @transaction.atomic
    def apply_referral_code(referred_user, code: str) -> tuple[bool, str]:
        code = code.strip().upper()
        rcode = ReferralCode.objects.filter(code=code, is_active=True).select_related("user").first()
        if not rcode:
            return False, "REF_CODE_NOT_FOUND"

        if rcode.user_id == referred_user.id:
            return False, "SELF_REFERRAL"

        if Referral.objects.filter(referred=referred_user).exists():
            return False, "ALREADY_REFERRED"

        Referral.objects.create(referrer=rcode.user, referred=referred_user, referral_code=rcode)
        return True, "OK"

    @staticmethod
    @transaction.atomic
    def try_qualify_and_reward(order: Order) -> None:
        """
        Called when an order becomes PAID.
        """
        if order.status != "PAID":
            return
        if order.total_amount < ReferralService.REFERRAL_MIN_ORDER:
            return

        referral = Referral.objects.filter(referred=order.user, status=Referral.Status.PENDING).select_related("referrer").first()
        if not referral:
            return

        # mark qualified
        referral.status = Referral.Status.QUALIFIED
        referral.qualified_order = order
        referral.qualified_at = timezone.now()
        referral.save(update_fields=["status", "qualified_order", "qualified_at"])

        # reward (credit) to referrer
        RewardLedger.objects.create(
            user=referral.referrer,
            source_type=RewardLedger.SourceType.REFERRAL,
            source_id=str(referral.id),
            amount=ReferralService.REFERRAL_REWARD,
        )

        referral.status = Referral.Status.REWARDED
        referral.rewarded_at = timezone.now()
        referral.save(update_fields=["status", "rewarded_at"])


class LoyaltyService:
    STAMPS_TARGET = 8  # 8 plats payés -> 1 bon
    VOUCHER_MAX_VALUE = Decimal("2000.00")
    VOUCHER_DAYS_VALID = 30

    @staticmethod
    def _paid_meals_count(order: Order) -> int:
        # count per-item quantities; adjust logic if you only want "orders" not "meals"
        return sum(OrderItem.objects.filter(order=order).values_list("quantity", flat=True))

    @staticmethod
    @transaction.atomic
    def on_order_paid(order: Order) -> None:
        if order.status != "PAID":
            return

        acc, _ = LoyaltyAccount.objects.get_or_create(user=order.user)
        add = LoyaltyService._paid_meals_count(order)
        acc.stamps += max(0, int(add))
        acc.save(update_fields=["stamps", "updated_at"])

        # issue vouchers while stamps allow it
        while acc.stamps >= LoyaltyService.STAMPS_TARGET:
            acc.stamps -= LoyaltyService.STAMPS_TARGET
            acc.save(update_fields=["stamps", "updated_at"])

            FreeItemVoucher.objects.create(
                user=order.user,
                max_item_value=LoyaltyService.VOUCHER_MAX_VALUE,
                expires_at=timezone.now() + timezone.timedelta(days=LoyaltyService.VOUCHER_DAYS_VALID),
            )

    @staticmethod
    @transaction.atomic
    def redeem_voucher(user, order: Order, voucher_id: int) -> tuple[bool, str, Decimal]:
        v = FreeItemVoucher.objects.select_for_update().filter(id=voucher_id, user=user).first()
        if not v:
            return False, "VOUCHER_NOT_FOUND", Decimal("0.00")
        if v.status != FreeItemVoucher.Status.AVAILABLE:
            return False, "VOUCHER_NOT_AVAILABLE", Decimal("0.00")
        if v.expires_at <= timezone.now():
            v.status = FreeItemVoucher.Status.EXPIRED
            v.save(update_fields=["status"])
            return False, "VOUCHER_EXPIRED", Decimal("0.00")

        # discount = min(price of cheapest item, max_item_value)
        items = list(OrderItem.objects.filter(order=order).select_related("meal"))
        if not items:
            return False, "EMPTY_ORDER", Decimal("0.00")

        cheapest_unit = min(i.unit_price for i in items)
        discount = min(cheapest_unit, v.max_item_value)

        order.discount_amount = (order.discount_amount or Decimal("0.00")) + discount
        order.total_amount = max(Decimal("0.00"), (order.subtotal_amount - order.discount_amount))
        order.save(update_fields=["discount_amount", "total_amount"])

        v.status = FreeItemVoucher.Status.USED
        v.used_order = order
        v.save(update_fields=["status", "used_order"])
        return True, "OK", discount
