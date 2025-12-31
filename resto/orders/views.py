from django.shortcuts import redirect, render

from marketing.models import LoyaltyAccount
from orders.loyalty import count_meals
from .cart import Cart
from comptes.models import UserProfile
from .models import FreeMealVoucher, Order, OrderItem
from .forms import CheckoutForm
from django.contrib.auth.decorators import login_required
from orders.cart import Cart
from django.views.decorators.http import require_POST

from django.db import transaction

@require_POST
def cart_add(request, meal_id):
    cart = Cart(request)
    cart.add(meal_id=meal_id, quantity=1)
    return redirect('orders:cart_detail')


def cart_remove(request, meal_id):
    cart = Cart(request)
    cart.remove(meal_id)
    return redirect('orders:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    promo_msg = request.session.pop("promo_msg", None)
    promo_ok = request.session.pop("promo_ok", None)
    return render(request, "orders/cart_detail.html", {
        "cart": cart,
        "promo_msg": promo_msg,
        "promo_ok": promo_ok,
    })


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


@login_required(login_url='login')
def checkout(request):
    cart = Cart(request)
    if not list(cart):
        return redirect('shop:meal_list')

    # Toujours avoir un profil disponible
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Mettre à jour le profil
            profile.full_name = form.cleaned_data['customer_name']
            profile.phone = form.cleaned_data['phone']
            profile.address = form.cleaned_data['address']
            profile.save()

            # Créer la commande
            order = Order.objects.create(
                user=request.user,
                customer_name=profile.full_name,
                phone=profile.phone,
                address=profile.address,
                total=cart.get_total_price(),
            )

            voucher = FreeMealVoucher.objects.filter(
                user=request.user,
                is_used=False
            ).first()

            if voucher:
                # appliquer remise équivalente à 1 plat
                voucher.is_used = True
                voucher.used_order = order
                voucher.save()

            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    meal=item['meal'],
                    quantity=item['quantity'],
                    unit_price=item['meal'].price
                )

            cart.clear()
            return render(request, 'orders/checkout_success.html', {'order': order})
    else:
        form = CheckoutForm(initial={
            'customer_name': profile.full_name,
            'phone': profile.phone,
            'address': profile.address,
        })

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'form': form,
    })






@transaction.atomic
def apply_loyalty_on_delivery(order):
    if not order.user:
        return  # invité = pas de fidélité

    account, _ = LoyaltyAccount.objects.get_or_create(user=order.user)

    meals = count_meals(order)
    account.points += meals

    free_count = account.points // 8
    account.points = account.points % 8
    account.save()

    for _ in range(free_count):
        FreeMealVoucher.objects.create(user=order.user)
