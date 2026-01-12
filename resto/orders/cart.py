from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from shop.models import Meal, MealVariant
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

    def _key(self, meal_id: int, variant_code: str) -> str:
        return f"{meal_id}:{variant_code}"

    def add(self, meal_id, variant_code="standard", quantity=1):
        meal_id = int(meal_id)
        variant_code = (variant_code or "standard").strip()

        meal = Meal.objects.get(id=meal_id)
        variant = MealVariant.objects.get(meal_id=meal_id, code=variant_code, is_active=True)

        key = self._key(meal_id, variant_code)

        if key not in self.cart:
            self.cart[key] = {
                "meal_id": meal_id,
                "variant": variant_code,
                "quantity": 0,
                "unit_price": int(variant.price),  # FCFA int
            }

        current = int(self.cart[key]["quantity"])
        wanted = current + int(quantity)

        limit_stock = int(variant.stock)
        limit_per_order = int(meal.max_per_order or self.MAX_QTY)
        hard_limit = min(self.MAX_QTY, limit_per_order, limit_stock)

        self.cart[key]["quantity"] = max(1, min(wanted, hard_limit))
        # keep price synced (au cas où admin change)
        self.cart[key]["unit_price"] = int(variant.price)

        self.save()

    def set(self, meal_id, variant_code="standard", quantity=1):
        meal_id = int(meal_id)
        variant_code = (variant_code or "standard").strip()
        qty = int(quantity)

        key = self._key(meal_id, variant_code)

        if qty <= 0:
            if key in self.cart:
                del self.cart[key]
                self.save()
            return

        meal = Meal.objects.get(id=meal_id)
        variant = MealVariant.objects.get(meal_id=meal_id, code=variant_code, is_active=True)

        if key not in self.cart:
            self.cart[key] = {
                "meal_id": meal_id,
                "variant": variant_code,
                "quantity": 0,
                "unit_price": int(variant.price),
            }

        limit_stock = int(variant.stock)
        limit_per_order = int(meal.max_per_order or self.MAX_QTY)
        hard_limit = min(self.MAX_QTY, limit_per_order, limit_stock)

        self.cart[key]["quantity"] = max(1, min(qty, hard_limit))
        self.cart[key]["unit_price"] = int(variant.price)
        self.save()

    def remove(self, meal_id, variant_code="standard"):
        key = self._key(int(meal_id), (variant_code or "standard").strip())
        if key in self.cart:
            del self.cart[key]
            self.save()

    def clear(self):
        self.session[CART_SESSION_ID] = {}
        self.remove_promo()
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        keys = list(self.cart.keys())

        # --- AUTO-UPGRADE anciens paniers ---
        upgraded = False
        for k in keys:
            item = self.cart.get(k) or {}
            # ancien format: {"quantity": X} avec key = meal_id
            if "meal_id" not in item:
                try:
                    meal_id = int(k)  # k était "12"
                except Exception:
                    continue
                variant_code = "standard"
                # initialise au nouveau format
                self.cart[f"{meal_id}:{variant_code}"] = {
                    "meal_id": meal_id,
                    "variant": variant_code,
                    "quantity": int(item.get("quantity", 1) or 1),
                    "unit_price": 0,  # sera recalculé via MealVariant
                }
                # supprime l'ancien
                del self.cart[k]
                upgraded = True

        if upgraded:
            self.save()

        # recalc keys après upgrade
        keys = list(self.cart.keys())
        if not keys:
            return

        meal_ids = {int(self.cart[k]["meal_id"]) for k in keys}
        meals = Meal.objects.filter(id__in=meal_ids)
        meal_map = {m.id: m for m in meals}

        variant_pairs = {(int(self.cart[k]["meal_id"]), self.cart[k]["variant"]) for k in keys}

        variants = MealVariant.objects.filter(
            meal_id__in=[p[0] for p in variant_pairs],
            code__in=[p[1] for p in variant_pairs],
            is_active=True
        )
        var_map = {(v.meal_id, v.code): v for v in variants}

        for k in keys:
            item = self.cart.get(k) or {}
            meal_id = int(item["meal_id"])
            variant_code = item["variant"]

            meal = meal_map.get(meal_id)
            variant = var_map.get((meal_id, variant_code))
            if not meal or not variant:
                continue

            qty = int(item.get("quantity", 1))
            unit_price = Decimal(str(int(variant.price)))
            total_price = unit_price * qty

            # sync price en session
            item["unit_price"] = int(variant.price)
            self.cart[k] = item

            yield {
                "key": k,
                "meal": meal,
                "variant": variant,
                "variant_code": variant_code,
                "quantity": qty,
                "unit_price": unit_price,
                "total_price": total_price,
            }


    def get_subtotal_price(self):
        total = Decimal("0")
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
        subtotal = self.get_subtotal_price()
        res = PromoService.estimate(user, subtotal, promo_code)

        if not res.ok:
            self.remove_promo()
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

    def __len__(self):
        return sum(int(item.get("quantity", 0)) for item in self.cart.values())
