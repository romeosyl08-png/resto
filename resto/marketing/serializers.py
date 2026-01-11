from rest_framework import serializers
from .models import FreeItemVoucher


class PromoApplySerializer(serializers.Serializer):
    promo_code = serializers.CharField(max_length=32)


class ReferralApplySerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=24)


class VoucherRedeemSerializer(serializers.Serializer):
    voucher_id = serializers.IntegerField(min_value=1)


class VoucherSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreeItemVoucher
        fields = ["id", "max_item_value", "expires_at", "status", "created_at"]
