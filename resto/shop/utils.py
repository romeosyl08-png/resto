from .models import Meal, MealVariant
from enum import Enum
from datetime import time, timedelta
from django.utils import timezone

# Horaires
PREOPEN_TIME = time(12, 0)
OPEN_TIME    = time(18, 30)
CUTOFF_TIME  = time(12, 0)  # fin des commandes du jour (wrap-around minuit)

WEEKDAYS = [
    (0, "Lundi"),
    (1, "Mardi"),
    (2, "Mercredi"),
    (3, "Jeudi"),
    (4, "Vendredi"),
    (5, "Samedi"),
    (6, "Dimanche"),
]

class OrderPhase(Enum):
    INACTIVE = "inactive"
    SOLDOUT  = "soldout"
    PREOPEN  = "preopen"
    OPEN     = "open"
    CLOSED   = "closed"


def time_in_range(start: time, end: time, now: time) -> bool:
    """
    Retourne True si now est dans l'intervalle [start, end)
    Supporte les intervalles qui traversent minuit
    """
    if start <= end:
        return start <= now < end
    else:
        return now >= start or now < end


def resolve_order_phase(*, now_time: time, meal=None, variants=None) -> OrderPhase:
    """
    Renvoie la phase de commande actuelle pour un plat donné
    """
    variants = variants or []

    if not meal or not meal.is_active:
        return OrderPhase.INACTIVE

    any_stock = any(v.stock > 0 for v in variants)
    if not any_stock:
        return OrderPhase.SOLDOUT

    if time_in_range(PREOPEN_TIME, OPEN_TIME, now_time):
        return OrderPhase.PREOPEN

    if time_in_range(OPEN_TIME, CUTOFF_TIME, now_time):
        return OrderPhase.OPEN

    return OrderPhase.CLOSED




def service_date(now_dt):
    # après 18h → menu du lendemain
    return (now_dt.date() + timedelta(days=1)) if now_dt.time() >= OPEN_TIME else now_dt.date()


DEFAULT_VARIANTS = [
    {"code": "basic", "label": "Basic", "price": 500},
    {"code": "standard", "label": "Standard", "price": 1000},
    {"code": "premium", "label": "Premium", "price": 1500},
]

def ensure_meal_variants(meal):
    if meal.variants.exists():
        return

    MealVariant.objects.bulk_create([
        MealVariant(
            meal=meal,
            code=v["code"],
            label=v["label"],
            price=v["price"],
            stock=0,
            is_active=True
        )
        for v in DEFAULT_VARIANTS
    ])


def sync_meal_availability():
    today = service_date(timezone.localtime()).weekday()

    for meal in Meal.objects.all():
        available = today in (meal.available_weekdays or [])
        if meal.is_active != available:
            meal.is_active = available
            meal.save(update_fields=["is_active"])
