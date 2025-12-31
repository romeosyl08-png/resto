from django.urls import path
from .views import (
    ApplyPromoView, ApplyReferralView, MyReferralCodeView,
    LoyaltyStatusView, RedeemVoucherView
)

urlpatterns = [
    path("orders/<int:order_id>/promo/apply/", ApplyPromoView.as_view()),
    path("referral/apply/", ApplyReferralView.as_view()),
    path("referral/my-code/", MyReferralCodeView.as_view()),
    path("loyalty/status/", LoyaltyStatusView.as_view()),
    path("orders/<int:order_id>/loyalty/redeem/", RedeemVoucherView.as_view()),
]
