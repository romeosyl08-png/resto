from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from orders.models import Order
from .serializers import PromoApplySerializer, ReferralApplySerializer, VoucherRedeemSerializer
from .models import LoyaltyAccount
from .services import PromoService, LoyaltyService


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
        loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
        loyalty.recompute()
        return Response({
            "points": loyalty.points,
            "next_discount_in": max(0, 10 - loyalty.points),
        })


class RedeemVoucherView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, order_id: int):
        ser = VoucherRedeemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        order = get_object_or_404(Order, id=order_id, user=request.user, status="DRAFT")
        ok, reason, discount = LoyaltyService.apply_best_reward_to_order(request.user, order)
        return Response({"ok": ok, "reason": reason, "discount": str(discount)})
 
