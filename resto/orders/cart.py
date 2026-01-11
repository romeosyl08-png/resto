from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from shop.models import Meal

from marketing.services import PromoService

CART_SESSION_ID = "cart"
PROMO_SESSION_KEY = "cart_promo"


class Cart:
    MAX_QTY = 20

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_ID)
        if not cart:
            cart = self.session[CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, meal_id, quantity=1):
        meal_id = str(meal_id)
        meal = Meal.objects.get(id=int(meal_id))

        if meal_id not in self.cart:
            self.cart[meal_id] = {"quantity": 0}

        current = int(self.cart[meal_id]["quantity"])
        wanted = current + int(quantity)

        limit_stock = int(meal.stock)
        limit_per_order = int(meal.max_per_order or self.MAX_QTY)
        hard_limit = min(self.MAX_QTY, limit_per_order, limit_stock)

        self.cart[meal_id]["quantity"] = max(1, min(wanted, hard_limit))
        self.save()

    def set(self, meal_id, quantity):
        meal_id = str(meal_id)
        qty = int(quantity)

        if qty <= 0:
            if meal_id in self.cart:
                del self.cart[meal_id]
            self.save()
            return

        meal = Meal.objects.get(id=int(meal_id))
        limit_stock = int(meal.stock)
        limit_per_order = int(meal.max_per_order or self.MAX_QTY)
        hard_limit = min(self.MAX_QTY, limit_per_order, limit_stock)

        if meal_id not in self.cart:
            self.cart[meal_id] = {"quantity": 0}

        self.cart[meal_id]["quantity"] = max(1, min(qty, hard_limit))
        self.save()

    def remove(self, meal_id):
        meal_id = str(meal_id)
        if meal_id in self.cart:
            del self.cart[meal_id]
            self.save()

    def clear(self):
        self.session[CART_SESSION_ID] = {}
        self.remove_promo()
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
                quantity = int(item["quantity"])
                yield {
                    "meal": meal,
                    "quantity": quantity,
                    "price": meal.price,
                    "total_price": meal.price * quantity,
                }

    def get_subtotal_price(self):
        total = Decimal("0.00")
        for item in self:
            total += item["total_price"]
        return total

    # -------- PROMO SESSION --------

    @property
    def promo_code(self):
        promo = self.session.get(PROMO_SESSION_KEY) or {}
        return promo.get("code")

    def get_discount_amount(self):
        promo = self.session.get(PROMO_SESSION_KEY) or {}
        try:
            return Decimal(str(promo.get("discount", "0")))
        except Exception:
            return Decimal("0.00")

    def get_total_after_discount(self):
        subtotal = self.get_subtotal_price()
        discount = self.get_discount_amount()
        if discount < 0:
            discount = Decimal("0.00")
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
        Utilise marketing.services.PromoService pour valider et calculer.
        """
        subtotal = self.get_subtotal_price()
        res = PromoService.estimate(user, subtotal, promo_code)

        if not res.ok:
            self.remove_promo()
            # message user-friendly
            mapping = {
                "EMPTY_CODE": "Code vide.",
                "INVALID_OR_EXPIRED": "Code invalide ou expiré.",
                "LOGIN_REQUIRED": "Connexion requise pour ce code.",
                "NOT_ELIGIBLE": "Vous n'êtes pas éligible à ce code.",
                "MIN_ORDER_NOT_MET": "Panier minimum non atteint.",
                "PROMO_LIMIT_REACHED": "Limite globale atteinte.",
                "USER_LIMIT_REACHED": "Limite d'utilisation atteinte.",
                "NO_DISCOUNT": "Ce code ne donne aucune remise.",
            }
            return False, mapping.get(res.reason, "Code promo refusé.")

        self.session[PROMO_SESSION_KEY] = {
            "code": res.code,
            "discount": str(res.discount),
            "applied_at": timezone.now().isoformat(),
        }
        self.save()
        return True, "Code appliqué."
