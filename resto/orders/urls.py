from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path("cart/", views.cart_detail, name="cart_detail"),

    path("cart/promo/apply/", views.cart_apply_promo, name="cart_apply_promo"),
    path("cart/promo/remove/", views.cart_remove_promo, name="cart_remove_promo"),

    # ADD : meal + variant
    path("cart/add/<int:meal_id>/", views.cart_add, name="cart_add"),

    # UPDATE : suppléments d'un article existant
    path(
        "cart/update-supplements/<int:meal_id>/<str:variant_code>/",
        views.cart_update_supplements,
        name="cart_update_supplements",
    ),

    # REMOVE : meal + variant (OBLIGATOIRE)
    path("cart/remove/<int:meal_id>/<str:variant_code>/", views.cart_remove, name="cart_remove"),

    path("checkout/", views.checkout, name="checkout"),
]
