from django.shortcuts import redirect, render
from .cart import Cart
from comptes.models import UserProfile
from .models import Order, OrderItem
from .forms import CheckoutForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from decimal import Decimal
from shop.models import MealVariant
from django.utils import timezone
from marketing.services import PromoService, LoyaltyService
from shop.utils import is_order_window_open
from django.db import transaction
from django.db.models import F
from django.contrib import messages


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

    now = timezone.localtime()
    order_window_open = is_order_window_open(now.time())

    res = cart.purge_unavailable(order_window_open=order_window_open)

    if res["removed"] > 0:
        if "closed" in res["reasons"]:
            messages.warning(request, "Commandes fermées : panier vidé automatiquement.")
        elif "stock" in res["reasons"] or "inactive" in res["reasons"]:
            messages.warning(request, "Certains articles n’étaient plus disponibles : ils ont été retirés du panier.")
        else:
            messages.warning(request, "Panier nettoyé.")

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
    now = timezone.localtime()
    order_window_open = is_order_window_open(now.time())

    res = cart.purge_unavailable(order_window_open=order_window_open)
    if res["removed"] > 0:
        return redirect("orders:cart_detail")

    if not list(cart):
        return redirect("shop:meal_list")

    now = timezone.localtime()
    if not is_order_window_open(now.time()):
        messages.error(request, "Commandes fermées. Reviens à l’ouverture.")
        return redirect("orders:cart_detail")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if not form.is_valid():
            return render(request, "orders/checkout.html", {"cart": cart, "form": form})

        # MAJ profil
        profile.full_name = form.cleaned_data["customer_name"]
        profile.phone = form.cleaned_data["phone"]
        profile.address = form.cleaned_data["address"]
        profile.save()

        promo_code = request.POST.get("promo_code", "").strip()

        # -------- TRANSACTION ATOMIQUE --------
        with transaction.atomic():
            # 1) Re-check stock + lock lignes variants
            locked = {}
            for item in cart:
                v = MealVariant.objects.select_for_update().get(
                    meal_id=item["meal"].id,
                    code=item["variant_code"],
                    is_active=True,
                )
                if v.stock < item["quantity"]:
                    messages.error(
                        request,
                        f"Stock insuffisant pour « {item['meal'].name} ({v.code}) »."
                    )
                    return redirect("orders:cart_detail")
                locked[(v.meal_id, v.code)] = v

            # 2) Créer commande
            order = Order.objects.create(
                user=request.user,
                customer_name=profile.full_name,
                phone=profile.phone,
                address=profile.address,
                subtotal=Decimal("0.00"),
                discount_total=Decimal("0.00"),
                total=Decimal("0.00"),
            )

            # 3) Créer items (prix du variant)
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    meal=item["meal"],
                    variant_code=item["variant_code"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                )

            # 4) Décrément stock (safe, via F())
            for item in cart:
                MealVariant.objects.filter(
                    meal_id=item["meal"].id,
                    code=item["variant_code"],
                    is_active=True,
                ).update(stock=F("stock") - item["quantity"])

            # 5) Totaux
            order.recompute_subtotal()
            order.save(update_fields=["subtotal", "total"])

            # 6) Promo / fidélité (si ces services modifient DB, c’est mieux dans la transaction)
            if promo_code:
                PromoService.apply_to_order(request.user, order, promo_code)

            LoyaltyService.apply_best_voucher_to_order(request.user, order)
            print("voucher applied? discount_total=", order.discount_total, "total=", order.total)
            print("items:", list(order.items.values_list("meal_id","variant_code","unit_price","quantity")))


        # -------- FIN TRANSACTION --------
            
            used_voucher = FreeItemVoucher.objects.filter(used_order=order).exists()
            return render(request, "orders/checkout_success.html", {"order": order, "used_voucher": used_voucher})

    else:
        form = CheckoutForm(initial={
            "customer_name": profile.full_name,
            "phone": profile.phone,
            "address": profile.address,
        })
        return render(request, "orders/checkout.html", {"cart": cart, "form": form})
