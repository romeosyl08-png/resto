from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from shop.models import Meal, MealVariant, Supplement
from marketing.services import PromoService

CART_SESSION_ID = "cart"
PROMO_SESSION_KEY = "cart_promo"


class Cart:
    MAX_QTY = 20

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.get(CART_SESSION_ID, {})
        self.session[CART_SESSION_ID] = self.cart

    def _key(self, meal_id: int, variant_code: str) -> str:
        return f"{meal_id}:{variant_code}"

    # ---------- CORE ----------

    def _recompute_item(self, item: dict) -> None:
        qty = int(item["quantity"])
        unit_price = Decimal(item["unit_price"])

        base = unit_price * qty
        supplements_total = Decimal("0.00")

        for sup in item.get("supplements", []):
            supplements_total += (
                Decimal(sup["unit_price"])
                * int(sup.get("quantity", 1))
                * qty
            )

        item["total_price"] = str(base + supplements_total)

    def save(self):
        self.session.modified = True

    # ---------- ADD / SET ----------

    def add(self, meal_id, variant_code="standard", quantity=1, supplements=None):
        meal_id = int(meal_id)
        variant_code = (variant_code or "standard").strip()
        quantity = max(1, int(quantity))

        key = self._key(meal_id, variant_code)

        if key not in self.cart:
            variant = MealVariant.objects.get(
                meal_id=meal_id, code=variant_code, is_active=True
            )
            self.cart[key] = {
                "meal_id": meal_id,
                "variant_code": variant_code,
                "quantity": 0,
                "unit_price": str(variant.price),
                "supplements": supplements or [],
                "total_price": "0.00",
            }

        self.cart[key]["quantity"] += quantity
        self._recompute_item(self.cart[key])
        self.save()

    def set(self, meal_id, variant_code="standard", quantity=1):
        meal_id = int(meal_id)
        variant_code = (variant_code or "standard").strip()
        quantity = int(quantity)

        key = self._key(meal_id, variant_code)

        if quantity <= 0:
            self.cart.pop(key, None)
            self.save()
            return

        variant = MealVariant.objects.get(
            meal_id=meal_id, code=variant_code, is_active=True
        )
        meal = Meal.objects.get(id=meal_id)

        limit = min(
            self.MAX_QTY,
            int(meal.max_per_order or self.MAX_QTY),
            int(variant.stock),
        )

        if key not in self.cart:
            self.cart[key] = {
                "meal_id": meal_id,
                "variant_code": variant_code,
                "quantity": 0,
                "unit_price": str(variant.price),
                "supplements": [],
                "total_price": "0.00",
            }

        self.cart[key]["quantity"] = max(1, min(quantity, limit))
        self.cart[key]["unit_price"] = str(variant.price)
        self._recompute_item(self.cart[key])
        self.save()

    def set_supplements(self, meal_id, variant_code, supplements: dict):
        key = self._key(int(meal_id), (variant_code or "standard").strip())
        if key not in self.cart:
            return

        valid = Supplement.objects.filter(
            id__in=supplements.keys(), is_active=True
        ).in_bulk()

        cleaned = []
        for sid, qty in supplements.items():
            sup = valid.get(int(sid))
            if not sup:
                continue
            cleaned.append({
                "id": sup.id,
                "name": sup.name,
                "quantity": max(1, int(qty)),
                "unit_price": str(sup.price),
            })

        self.cart[key]["supplements"] = cleaned
        self._recompute_item(self.cart[key])
        self.save()

    # ---------- REMOVE ----------

    def remove(self, meal_id, variant_code="standard"):
        key = self._key(int(meal_id), (variant_code or "standard").strip())
        self.cart.pop(key, None)
        self.save()

    def clear(self):
        self.session[CART_SESSION_ID] = {}
        self.remove_promo()
        self.save()

    # ---------- ITER ----------

    def __iter__(self):
        meal_ids = [i["meal_id"] for i in self.cart.values()]
        meals = {m.id: m for m in Meal.objects.filter(id__in=meal_ids)}

        for item in self.cart.values():
            meal = meals.get(item["meal_id"])
            if not meal:
                continue

            yield {
                "meal": meal,
                "meal_id": item["meal_id"],
                "variant_code": item["variant_code"],
                "quantity": int(item["quantity"]),
                "unit_price": Decimal(item["unit_price"]),
                "total_price": Decimal(item["total_price"]),
                "supplements": [
                    {
                        **sup,
                        "unit_price": Decimal(sup["unit_price"]),
                        "total": Decimal(sup["unit_price"])
                        * int(sup["quantity"])
                        * int(item["quantity"]),
                    }
                    for sup in item.get("supplements", [])
                ],
            }

    def __len__(self):
        return sum(int(i["quantity"]) for i in self.cart.values())

    # ---------- TOTALS ----------

    def get_subtotal_price(self):
        return sum(item["total_price"] for item in self)

    # ---------- PROMO ----------

    def remove_promo(self):
        self.session.pop(PROMO_SESSION_KEY, None)
        self.save()

    def apply_promo(self, user, promo_code: str):
        subtotal = self.get_subtotal_price()
        res = PromoService.estimate(user, subtotal, promo_code)

        if not res.ok:
            self.remove_promo()
            return False, res.reason

        self.session[PROMO_SESSION_KEY] = {
            "code": res.code,
            "discount": str(res.discount),
            "applied_at": timezone.now().isoformat(),
        }
        self.save()
        return True, "Code appliqué"

    def get_discount_amount(self):
        promo = self.session.get(PROMO_SESSION_KEY, {})
        return Decimal(promo.get("discount", "0.00"))

    @property
    def promo_code(self):
        promo = self.session.get(PROMO_SESSION_KEY, {})
        return promo.get("code")

    def get_total_after_discount(self):
        subtotal = self.get_subtotal_price()
        discount = self.get_discount_amount()
        return max(
            Decimal("0.00"),
            subtotal - discount
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)
