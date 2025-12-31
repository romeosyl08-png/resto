from decimal import Decimal
from comptes.models import Meal
from marketing.models import Promotion, PromotionRedemption  # adapte l'import si besoin
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone


CART_SESSION_ID = "cart"
PROMO_SESSION_KEY = "cart_promo"


PROMO_SESSION_KEY = "cart_promo"
CART_SESSION_ID = "cart"


class Cart:
    MAX_QTY = 20  # plafond global (ajuste si besoin)

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_ID)
        if not cart:
            cart = self.session[CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, meal_id, quantity=1):
        """Incrémente la quantité (min 1, max MAX_QTY)."""
        meal_id = str(meal_id)

        if meal_id not in self.cart:
            self.cart[meal_id] = {"quantity": 0}

        new_qty = self.cart[meal_id]["quantity"] + int(quantity)
        self.cart[meal_id]["quantity"] = max(1, min(self.MAX_QTY, new_qty))
        self.save()

    def set(self, meal_id, quantity):
        """Fixe la quantité (0 => suppression)."""
        meal_id = str(meal_id)
        qty = int(quantity)

        if qty <= 0:
            if meal_id in self.cart:
                del self.cart[meal_id]
        else:
            if meal_id not in self.cart:
                self.cart[meal_id] = {"quantity": 0}
            self.cart[meal_id]["quantity"] = max(1, min(self.MAX_QTY, qty))

        self.save()

    def remove(self, meal_id):
        meal_id = str(meal_id)
        if meal_id in self.cart:
            del self.cart[meal_id]
            self.save()

    def clear(self):
        self.session[CART_SESSION_ID] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        meal_ids = self.cart.keys()
        meals = Meal.objects.filter(id__in=meal_ids)
        meal_map = {str(m.id): m for m in meals}

        for meal_id, item in self.cart.items():
            meal = meal_map.get(meal_id)
            if meal:
                quantity = item["quantity"]
                total_price = meal.price * quantity
                yield {
                    "meal": meal,
                    "quantity": quantity,
                    "price": meal.price,
                    "total_price": total_price,
                }

    def get_total_price(self):
        total = Decimal("0")
        for item in self:
            total += item["total_price"]
        return total

    def __len__(self):
        return sum(item["quantity"] for item in self.cart.values())
    

    # ---------- PROMO (MVP) ----------

    @property
    def promo_code(self):
        promo = self.session.get(PROMO_SESSION_KEY) or {}
        return promo.get("code")

    def get_subtotal_price(self):
        # ton total actuel = sous-total (sans remise)
        return self.get_total_price()

    def get_discount_amount(self):
        promo = self.session.get(PROMO_SESSION_KEY) or {}
        try:
            return Decimal(str(promo.get("discount", "0")))
        except Exception:
            return Decimal("0")

    def get_total_after_discount(self):
        subtotal = self.get_subtotal_price()
        discount = self.get_discount_amount()
        if discount < 0:
            discount = Decimal("0")
        if discount > subtotal:
            discount = subtotal
        return (subtotal - discount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def remove_promo(self):
        if PROMO_SESSION_KEY in self.session:
            del self.session[PROMO_SESSION_KEY]
            self.save()

    def apply_promo(self, user, promo_code: str):
        """
        Applique une promo au panier (stockée en session).
        Retour: (ok: bool, message: str)
        """
        code = (promo_code or "").strip().upper()
        if not code:
            self.remove_promo()
            return False, "Code vide."

        promo = Promotion.objects.filter(code=code).first()
        if not promo or not promo.is_valid_now():
            self.remove_promo()
            return False, "Code invalide ou expiré."

        if promo.segment != Promotion.Segment.ALL and not user:
            self.remove_promo()
            return False, "Connexion requise pour ce code."

        subtotal = self.get_subtotal_price()

        if promo.min_order and subtotal < promo.min_order:
            self.remove_promo()
            return False, f"Panier minimum requis : {promo.min_order} FCFA."

        # Limites d’usage global / par utilisateur (optionnel mais recommandé)
        if promo.usage_limit_total is not None:
            used_total = PromotionRedemption.objects.filter(promotion=promo, status="APPLIED").count()
            if used_total >= promo.usage_limit_total:
                self.remove_promo()
                return False, "Ce code a atteint sa limite d'utilisation."

        if user and promo.usage_limit_per_user is not None:
            used_user = PromotionRedemption.objects.filter(promotion=promo, user=user, status="APPLIED").count()
            if used_user >= promo.usage_limit_per_user:
                self.remove_promo()
                return False, "Limite d'utilisation atteinte pour ce code."

        # Segment NEW / INACTIVE_30D (si tu veux l’activer)
        # Ici je garde simple. Si tu veux, je te branche la logique propre.

        # Calcul remise
        if promo.promo_type == Promotion.PromoType.PERCENT:
            discount = (subtotal * promo.value / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            discount = promo.value

        if promo.max_discount is not None:
            discount = min(discount, promo.max_discount)

        discount = min(discount, subtotal)
        if discount <= 0:
            self.remove_promo()
            return False, "Ce code ne donne aucune remise."

        # Stocker en session
        self.session[PROMO_SESSION_KEY] = {
            "code": promo.code,
            "discount": str(discount),
            "applied_at": timezone.now().isoformat(),
        }
        self.save()
        return True, "Code appliqué."


    def count_meals(order):
        return sum(item.quantity for item in order.items.all())
