from django.shortcuts import redirect, render
from .cart import Cart
from comptes.models import UserProfile
from .models import Address, Order, OrderItem, OrderItemSupplement
from .forms import CheckoutForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from decimal import Decimal
from shop.models import Product, ProductVariant, Supplement
from django.utils import timezone
from marketing.services import PromoService, LoyaltyService
from shop.utils import resolve_order_phase, OrderPhase
from .utils import build_cart_summary

from django.db import transaction
from django.db.models import F
from django.contrib import messages


@require_POST
def cart_add(request, product_id):
    """Ajoute un article au panier avec ses suppléments"""
    cart = Cart(request)
    variant_code = request.POST.get("variant", "standard")
    qty = int(request.POST.get("quantity", "1") or "1")
    qty = max(1, min(qty, 20))

    # Récupère les suppléments sélectionnés + quantités
    supplement_ids = request.POST.getlist("supplements")
    supplements = Supplement.objects.filter(id__in=supplement_ids, is_active=True)

    qty_map = {}
    for sid in supplement_ids:
        raw = request.POST.get(f"qty_{sid}", "1")
        try:
            qty_map[sid] = max(1, int(raw))
        except ValueError:
            qty_map[sid] = 1

    # FIX BUG #4 & #7: Transforme en dictionnaires avec string pour prix
    # et quantité issue du formulaire
    sup_list = [
        {
            "id": s.id,
            "name": s.name,
            "unit_price": str(s.price),  # FIX: string au lieu de float
            "quantity": qty_map.get(str(s.id), 1)
        }
        for s in supplements
    ]

    # Ajoute au panier
    cart.add(
        product_id=product_id,
        variant_code=variant_code,
        quantity=qty,
        supplements=sup_list
    )

    # FIX BUG #16: Message de confirmation
    messages.success(request, f"Article ajouté au panier (×{qty})")
    
    return redirect("orders:cart_detail")


def cart_remove(request, product_id, variant_code):
    """Supprime un article du panier"""
    cart = Cart(request)
    cart.remove(product_id, variant_code)
    
    # FIX BUG #16: Message de confirmation
    messages.info(request, "Article retiré du panier")
    
    return redirect("orders:cart_detail")


@require_POST
def cart_apply_promo(request):
    """Applique un code promo au panier"""
    cart = Cart(request)
    promo_code = request.POST.get("promo_code", "").strip()
    user = request.user if request.user.is_authenticated else None

    ok, msg = cart.apply_promo(user=user, promo_code=promo_code)
    request.session["promo_msg"] = msg
    request.session["promo_ok"] = ok
    return redirect("orders:cart_detail")


@require_POST
def cart_remove_promo(request):
    """Retire le code promo du panier"""
    cart = Cart(request)
    cart.remove_promo()
    request.session["promo_msg"] = "Code promo retiré."
    request.session["promo_ok"] = True
    return redirect("orders:cart_detail")


@require_POST
def cart_update_supplements(request, product_id, variant_code):
    """Met à jour les quantités de suppléments pour un item du panier"""
    cart = Cart(request)
    supplement_ids = request.POST.getlist("supplements")

    # map id -> quantity depuis champs type qty_12
    qty_map = {}
    for sid in supplement_ids:
        raw = request.POST.get(f"qty_{sid}", "1")
        try:
            qty = max(1, int(raw))
        except ValueError:
            qty = 1
        qty_map[sid] = qty

    cart.set_supplements(product_id, variant_code, qty_map)
    messages.success(request, "Suppléments mis à jour")
    return redirect("orders:cart_detail")


def cart_detail(request):
    """Affiche le contenu du panier"""
    cart = Cart(request)
    now = timezone.localtime()

    # Vérifie chaque item pour sa disponibilité
    removed = 0
    reasons = set()
    
    for item in list(cart.cart.values()):
        product = Product.objects.filter(id=item["product_id"]).first()
        if not product:
            # FIX BUG #15: Gestion explicite des repas manquants
            cart.remove(item["product_id"], item.get("variant_code", "standard"))
            removed += 1
            reasons.add("not_found")
            continue
            
        variant_code = item.get("variant_code", "standard")
        variants = ProductVariant.objects.filter(
            product_id=item["product_id"],
            code=variant_code,
            is_active=True
        )

        phase = resolve_order_phase(now_time=now.time(), product=product, variants=variants)
        ui = OrderPhase.OPEN if phase == OrderPhase.OPEN else phase
        
        if ui != OrderPhase.OPEN:
            cart.remove(item["product_id"], variant_code)
            removed += 1
            if phase in (OrderPhase.CLOSED, OrderPhase.PREOPEN):
                reasons.add("closed")
            elif phase == OrderPhase.SOLDOUT:
                reasons.add("stock")
            elif phase == OrderPhase.INACTIVE:
                reasons.add("inactive")

    # FIX BUG #16: Messages plus clairs
    if removed > 0:
        if "not_found" in reasons:
            messages.warning(request, f"{removed} article(s) supprimé(s) car introuvable(s).")
        elif "closed" in reasons:
            messages.warning(request, "Commandes fermées ou plat non commandable : panier nettoyé.")
        elif "stock" in reasons:
            messages.warning(request, "Certains articles n'étaient plus en stock.")
        elif "inactive" in reasons:
            messages.warning(request, "Certains articles ne sont plus disponibles.")
        else:
            messages.warning(request, f"{removed} article(s) retiré(s) du panier.")

    promo_msg = request.session.pop("promo_msg", None)
    promo_ok = request.session.pop("promo_ok", None)

    cart_summary = build_cart_summary(cart)

    return render(request, "orders/cart_detail.html", {
        "cart": cart,
        "cart_summary": cart_summary,
        "promo_msg": promo_msg,
        "promo_ok": promo_ok,
    })


@login_required(login_url="comptes:login")
def checkout(request):
    """Finalise la commande avec adresse unique"""
    cart = Cart(request)
    cart_summary = build_cart_summary(cart)
    now = timezone.localtime()

    if len(cart) == 0:
        messages.warning(request, "Votre panier est vide.")
        return redirect("shop:product_list")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Récupère l'adresse unique
    selected_address = profile.default_address

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)
        if not form.is_valid():
            return render(request, "orders/checkout.html", {
                "cart": cart,
                "cart_summary": cart_summary,
                "form": form,
                "address": selected_address,
            })
        if not selected_address:
            messages.error(request, "Aucune adresse enregistrée pour ce compte.")
            return redirect("comptes:add_address")

        # Met à jour le profil avec nom et téléphone
        profile.full_name = form.cleaned_data["customer_name"]
        profile.phone = form.cleaned_data["phone"]
        profile.save()

        # Préparer le texte de l'adresse pour la commande
        if selected_address.other:
            address_text = f"Autre endroit (livraison payante)\n{selected_address.other_detail}"
        else:
            address_text = f"{selected_address.get_room_display()} - {selected_address.sector}"

        promo_code = request.POST.get("promo_code", "").strip()

        try:
            with transaction.atomic():
                locked = {}
                # Vérification stock et phase pour chaque item
                for item in cart:
                    try:
                        v = ProductVariant.objects.select_for_update().get(
                            product_id=item["product"].id,
                            code=item["variant_code"],
                            is_active=True
                        )
                    except ProductVariant.DoesNotExist:
                        messages.error(
                            request,
                            f"La variante « {item['product'].name} ({item['variant_code']}) » n'existe plus."
                        )
                        return redirect("orders:cart_detail")

                    phase = resolve_order_phase(
                        now_time=now.time(),
                        product=item["product"],
                        variants=ProductVariant.objects.filter(
                            product_id=item["product"].id,
                            code=item["variant_code"],
                            is_active=True
                        )
                    )
                    if phase != OrderPhase.OPEN:
                        messages.error(
                            request,
                            f"Le plat « {item['product'].name} » n'est plus commandable."
                        )
                        return redirect("orders:cart_detail")

                    if v.stock < item["quantity"]:
                        messages.error(
                            request,
                            f"Stock insuffisant pour « {item['product'].name} ({v.code}) »."
                        )
                        return redirect("orders:cart_detail")

                    locked[(v.product_id, v.code)] = v

                # Créer la commande
                order = Order.objects.create(
                    user=request.user,
                    customer_name=profile.full_name,
                    phone=profile.phone,
                    address=address_text,
                    address_detail=selected_address.other_detail if selected_address.other else "",
                    subtotal=Decimal("0.00"),
                    discount_total=Decimal("0.00"),
                    total=Decimal("0.00"),
                )

                # Créer les items et leurs suppléments
                for item in cart:
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=item["product"],
                        variant_code=item["variant_code"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                    )
                    for sup in item.get("supplements", []):
                        try:
                            supplement_obj = Supplement.objects.get(id=sup["id"], is_active=True)
                            OrderItemSupplement.objects.create(
                                order_item=order_item,
                                supplement=supplement_obj,
                                quantity=sup["quantity"],
                                unit_price=Decimal(str(sup["unit_price"])),
                            )
                        except Supplement.DoesNotExist:
                            pass

                # Décrémente le stock
                for item in cart:
                    ProductVariant.objects.filter(
                        product_id=item["product"].id,
                        code=item["variant_code"],
                        is_active=True,
                    ).update(stock=F("stock") - item["quantity"])

                # Recalcule les totaux
                order.recompute_subtotal()
                order.save(update_fields=["subtotal", "total"])

                # Applique code promo si existant

                if promo_code:
                    PromoService.apply_to_order(
                        request.user,
                        order,
                        cart.promo_code
                    )

                # Applique le meilleur avantage fidélité (points)
                LoyaltyService.apply_best_reward_to_order(request.user, order)

            cart.clear()  # Vide le panier

            order = Order.objects.select_related("user").prefetch_related(
                "items__product",
                "items__supplements__supplement"
            ).get(pk=order.pk)

            order_items = []
            for it in order.items.all():
                supplements = []
                for sup in it.supplements.all():
                    supplements.append({
                        "name": sup.supplement.name,
                        "quantity": sup.quantity,
                        "subtotal": sup.subtotal(),
                    })
                order_items.append({
                    "product_name": it.product.name,
                    "variant_code": it.variant_code,
                    "quantity": it.quantity,
                    "unit_price": it.unit_price,
                    "subtotal": it.subtotal(),
                    "supplements": supplements,
                })

            order_summary = {
                "subtotal": order.subtotal,
                "discount_total": order.discount_total,
                "total": order.total,
                "promo_code": order.promo_code,
                "loyalty_reward": order.loyalty_reward,
                "loyalty_discount": order.loyalty_discount,
                "has_discount": (order.discount_total or Decimal("0.00")) > Decimal("0.00"),
            }

            return render(request, "orders/checkout_success.html", {
                "order": order,
                "order_items": order_items,
                "order_summary": order_summary,
                "loyalty_reward": order.loyalty_reward
            })

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception("Erreur lors du checkout")
            messages.error(request, "Une erreur s'est produite. Veuillez réessayer.")
            return redirect("orders:cart_detail")

    else:
        # GET : Préremplit le formulaire
        initial_data = {
            "customer_name": profile.full_name,
            "phone": profile.phone,
        }
        form = CheckoutForm(initial=initial_data, user=request.user)
        if not selected_address:
            messages.error(request, "Veuillez ajouter une adresse avant de commander.")
            return redirect("comptes:add_address")


        return render(request, "orders/checkout.html", {
            "cart": cart,
            "cart_summary": cart_summary,
            "form": form,
            "address": selected_address,  # passer l'adresse unique au template
        })
