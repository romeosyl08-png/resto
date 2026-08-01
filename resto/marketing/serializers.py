from rest_framework import serializers


class PromoApplySerializer(serializers.Serializer):
    promo_code = serializers.CharField(max_length=32)


class ReferralApplySerializer(serializers.Serializer):
    referral_code = serializers.CharField(max_length=24)


class VoucherRedeemSerializer(serializers.Serializer):
    voucher_id = serializers.IntegerField(min_value=1, required=False)


 
