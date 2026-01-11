from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from orders.models import Order
from .serializers import PromoApplySerializer, ReferralApplySerializer, VoucherRedeemSerializer, VoucherSerializer
from .services import PromoService, ReferralService, LoyaltyService
from .models import FreeItemVoucher


class ApplyPromoView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        ser = PromoApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=order_id, user=request.user, status="DRAFT")
        res = PromoService.apply_promo(
            request.user,
            order,
            ser.validated_data["promo_code"],
            device_id=request.headers.get("X-Device-Id"),
            ip_hash=request.headers.get("X-Ip-Hash"),
        )
        return Response({"ok": res.ok, "reason": res.reason, "discount": str(res.discount)})


class ApplyReferralView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = ReferralApplySerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        ok, reason = ReferralService.apply_referral_code(request.user, ser.validated_data["referral_code"])
        return Response({"ok": ok, "reason": reason})


class MyReferralCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = ReferralService.get_or_create_code(request.user)
        return Response({"code": code.code, "is_active": code.is_active})


class LoyaltyStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vouchers = FreeItemVoucher.objects.filter(user=request.user).order_by("-created_at")[:20]
        return Response({
            "vouchers": VoucherSerializer(vouchers, many=True).data
        })


class RedeemVoucherView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        ser = VoucherRedeemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=order_id, user=request.user, status="DRAFT")
        ok, reason, discount = LoyaltyService.redeem_voucher(request.user, order, ser.validated_data["voucher_id"])
        return Response({"ok": ok, "reason": reason, "discount": str(discount)})
