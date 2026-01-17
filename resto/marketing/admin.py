# marketing/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import (
    Promotion, PromotionRedemption,
    LoyaltyAccount, FreeItemVoucher,
)


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "promo_type", "value",
        "segment", "is_active",
        "start_at", "end_at",
        "min_order_amount", "max_discount_amount",
        "usage_limit_total", "usage_limit_per_user",
        "created_at",
    )
    list_filter = ("promo_type", "segment", "is_active")
    search_fields = ("code", "name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Base", {
            "fields": ("name", "code", "promo_type", "value", "segment", "is_active")
        }),
        ("Fenêtre de validité", {
            "fields": ("start_at", "end_at")
        }),
        ("Conditions", {
            "fields": ("min_order_amount", "max_discount_amount")
        }),
        ("Limites d'usage", {
            "fields": ("usage_limit_total", "usage_limit_per_user")
        }),
        ("Meta", {
            "fields": ("created_at",)
        }),
    )


@admin.register(PromotionRedemption)
class PromotionRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "promotion", "user", "order",
        "discount_amount", "status", "redeemed_at",
    )
    list_filter = ("status", "promotion")
    search_fields = ("promotion__code", "user__username", "user__email", "order__id")
    ordering = ("-redeemed_at",)
    readonly_fields = ("redeemed_at",)


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "count_500", "count_1000", "count_1500", "updated_at")
    search_fields = ("user__username", "user__email")
    ordering = ("-updated_at",)
    readonly_fields = ("updated_at",)


@admin.register(FreeItemVoucher)
class FreeItemVoucherAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "status",
        "tier_value", "expires_at",
        "used_order", "created_at", "is_expired",
    )
    list_filter = ("status", "tier_value")
    search_fields = ("user__username", "user__email", "used_order__id")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
    @admin.display(boolean=True, description="Expiré ?")
    def is_expired(self, obj):
        return bool(obj.expires_at and obj.expires_at <= timezone.now())
