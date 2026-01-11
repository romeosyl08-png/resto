from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


User = settings.AUTH_USER_MODEL


class Promotion(models.Model):
    class PromoType(models.TextChoices):
        PERCENT = "PERCENT", "Percent"
        FIXED_AMOUNT = "FIXED_AMOUNT", "Fixed amount"
        FREE_ITEM = "FREE_ITEM", "Free item"

    class Segment(models.TextChoices):
        ALL = "ALL", "All"
        NEW = "NEW", "New users"
        INACTIVE_30D = "INACTIVE_30D", "Inactive 30 days"

    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, unique=True)  # store uppercase
    promo_type = models.CharField(max_length=16, choices=PromoType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    min_order_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    segment = models.CharField(max_length=16, choices=Segment.choices, default=Segment.ALL)

    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    usage_limit_total = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_user = models.PositiveIntegerField(null=True, blank=True)

    non_cumulable = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_currently_valid(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        return True

    def __str__(self):
        return f"{self.code} ({self.promo_type})"


class PromotionRedemption(models.Model):
    class Status(models.TextChoices):
        APPLIED = "APPLIED", "Applied"
        CANCELLED = "CANCELLED", "Cancelled"
        REVERSED = "REVERSED", "Reversed"

    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name="redemptions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="promo_redemptions")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="promo_redemptions")

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    redeemed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPLIED)

    device_id = models.CharField(max_length=128, null=True, blank=True)
    ip_hash = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["promotion", "user", "status"]),
            models.Index(fields=["order"]),
        ]


class ReferralCode(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=24, unique=True)  # uppercase
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        QUALIFIED = "QUALIFIED", "Qualified"
        REWARDED = "REWARDED", "Rewarded"
        REJECTED = "REJECTED", "Rejected"

    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="referrals_made")
    referred = models.OneToOneField(User, on_delete=models.CASCADE, related_name="referral_received")
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name="referrals")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    qualified_order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="qualifying_referrals"
    )
    qualified_at = models.DateTimeField(null=True, blank=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(referrer=models.F("referred")), name="no_self_referral"),

        ]


class RewardLedger(models.Model):
    class SourceType(models.TextChoices):
        REFERRAL = "REFERRAL", "Referral"
        PROMO_ADJUST = "PROMO_ADJUST", "Promo adjust"
        COMPENSATION = "COMPENSATION", "Compensation"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reward_ledger")
    source_type = models.CharField(max_length=16, choices=SourceType.choices)
    source_id = models.CharField(max_length=64, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # + / -
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, default="ACTIVE")  # ACTIVE/EXPIRED/REVERSED

    class Meta:
        indexes = [models.Index(fields=["user", "created_at"])]


class LoyaltyAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="loyalty")
    stamps = models.PositiveIntegerField(default=0)  # number of paid meals counted
    updated_at = models.DateTimeField(auto_now=True)


class FreeItemVoucher(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        USED = "USED", "Used"
        EXPIRED = "EXPIRED", "Expired"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="free_vouchers")
    max_item_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)

    used_order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="used_vouchers"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "status", "expires_at"])]
