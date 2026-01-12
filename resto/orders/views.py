from django.shortcuts import redirect, render
from .cart import Cart
from comptes.models import UserProfile
from .models import Order, OrderItem
from .forms import CheckoutForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from decimal import Decimal
from shop.models import MealVariant

from marketing.services import PromoService, LoyaltyService


@require_POST
def cart_add(request, meal_id):
    cart = Cart(request)
    variant_code = request.POST.get("variant", "standard")
    qty = int(request.POST.get("quantity", "1") or "1")

    # validation + stock via Cart.add (qui check variant)
    cart.add(meal_id=meal_id, variant_code=variant_code, quantity=qty)
    return redirect("orders:cart_detail")



def cart_remove(request, meal_id, variant_code):
    cart = Cart(request)
    cart.remove(meal_id, variant_code)
    return redirect("orders:cart_detail")




@require_POST
def cart_apply_promo(request):
    cart = Cart(request)
    promo_code = request.POST.get("promo_code", "")
    user = request.user if request.user.is_authenticated else None

    ok, msg = cart.apply_promo(user=user, promo_code=promo_code)
    request.session["promo_msg"] = msg
    request.session["promo_ok"] = ok
    return redirect("orders:cart_detail")

@require_POST
def cart_remove_promo(request):
    cart = Cart(request)
    cart.remove_promo()
    request.session["promo_msg"] = "Code retiré."
    request.session["promo_ok"] = True
    return redirect("orders:cart_detail")

def cart_detail(request):
    cart = Cart(request)
    promo_msg = request.session.pop("promo_msg", None)
    promo_ok = request.session.pop("promo_ok", None)
    return render(request, "orders/cart_detail.html", {
        "cart": cart,
        "promo_msg": promo_msg,
        "promo_ok": promo_ok,
    })





@login_required(login_url="comptes:login")
def checkout(request):
    cart = Cart(request)
    if not list(cart):
        return redirect("shop:meal_list")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            profile.full_name = form.cleaned_data["customer_name"]
            profile.phone = form.cleaned_data["phone"]
            profile.address = form.cleaned_data["address"]
            profile.save()

            order = Order.objects.create(
                user=request.user,
                customer_name=profile.full_name,
                phone=profile.phone,
                address=profile.address,
                subtotal=Decimal("0.00"),
                discount_total=Decimal("0.00"),
                total=Decimal("0.00"),
            )


            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    meal=item["meal"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],   # <-- prix variante
                    variant_code=item["variant_code"],  # <-- si tu ajoutes ce champ
                )


            order.recompute_subtotal()
            order.save(update_fields=["subtotal", "total"])

            # 1) promo (si tu as un champ promo_code dans le form ou request.POST)
            promo_code = request.POST.get("promo_code", "").strip()
            if promo_code:
                PromoService.apply_to_order(request.user, order, promo_code)

            # 2) voucher (1 bon max)
            LoyaltyService.apply_best_voucher_to_order(request.user, order)

            cart.clear()
            return render(request, "orders/checkout_success.html", {"order": order})
    else:
        form = CheckoutForm(initial={
            "customer_name": profile.full_name,
            "phone": profile.phone,
            "address": profile.address,
        })

    return render(request, "orders/checkout.html", {"cart": cart, "form": form})
