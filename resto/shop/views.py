from django.shortcuts import render, get_object_or_404
from .models import Meal, Category
from django.shortcuts import render
from datetime import time, datetime, timedelta
from django.utils import timezone
from datetime import datetime, timedelta
from django.shortcuts import render
from django.utils import timezone

from .models import Meal, Category, MealVariant
#from .views_helpers import _is_order_window_open, _service_date   adapte si besoin
# ou garde tes fonctions dans le même fichier

# OPEN_TIME et CUTOFF_TIME doivent exister dans ce fichier
# OPEN_TIME = time(18, 0)
# CUTOFF_TIME = time(9, 30)

def meal_detail(request, slug):
    meal = get_object_or_404(Meal, slug=slug, is_active=True)
    return render(request, 'shop/meal_detail.html', {'meal': meal})





OPEN_TIME = time(18, 0)
CUTOFF_TIME = time(9, 30)

def _is_order_window_open(now_time: time) -> bool:
    return (now_time >= OPEN_TIME) or (now_time < CUTOFF_TIME)

def _service_date(now_dt):
    return (now_dt.date() + timedelta(days=1)) if now_dt.time() >= OPEN_TIME else now_dt.date()



def meal_list(request, category_slug=None):
    now = timezone.localtime()

    # TOUJOURS défini
    categories = Category.objects.all()

    order_window_open = _is_order_window_open(now.time())

    service_day = _service_date(now)
    service_weekday = service_day.weekday()

    # base queryset (si tu veux utiliser category_slug un jour)
    qs = Meal.objects.filter(is_active=True)

    # fallback weekdays
    try:
        Meal._meta.get_field("available_weekdays")
        has_weekdays = True
    except Exception:
        has_weekdays = False

    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    if has_weekdays:
        meals_today = [
            m for m in qs.order_by("-id")
            if service_weekday in (getattr(m, "available_weekdays", []) or [])
        ]
    else:
        meals_today = list(qs.order_by("-id"))

    meal_of_day = meals_today[0] if meals_today else None

    # variantes : TOUJOURS défini
    variants = []

    # auto-crée les 3 tarifs si meal existe mais pas de variantes
    if meal_of_day:
        if meal_of_day.variants.count() == 0:
            MealVariant.objects.bulk_create([
                MealVariant(meal=meal_of_day, code="basic", label="Basic", price=500, stock=0, is_active=True),
                MealVariant(meal=meal_of_day, code="standard", label="Standard", price=1000, stock=0, is_active=True),
                MealVariant(meal=meal_of_day, code="premium", label="Premium", price=1500, stock=0, is_active=True),
            ])

        variants = list(meal_of_day.variants.filter(is_active=True).order_by("price"))

    # --- NEXT OPEN / NEXT CUTOFF : TOUJOURS DÉFINIS ---
    today = now.date()

    if now.time() < OPEN_TIME:
        next_open_date = today
    else:
        next_open_date = today + timedelta(days=1)
    next_open_dt = timezone.make_aware(datetime.combine(next_open_date, OPEN_TIME))

    next_cutoff_dt = timezone.make_aware(datetime.combine(service_day, CUTOFF_TIME))

    # sold_out (version cohérente avec variantes)
    sold_out = True
    if meal_of_day:
        any_variant_in_stock = any(v.stock > 0 for v in variants) if variants else (meal_of_day.stock > 0)
        sold_out = (not order_window_open) or (not any_variant_in_stock) or (not meal_of_day.is_active)
        # shop/views.py (dans meal_list, après variants/any_variant_in_stock)
is_closed = not order_window_open
is_out_of_stock = bool(meal_of_day) and (not any_variant_in_stock)
is_inactive = (not meal_of_day) or (not meal_of_day.is_active)

sold_out = is_out_of_stock or is_inactive  # "sold out" = stock KO ou plat indispo, PAS horaire

status_msg = None
status_kind = None  # "closed" | "soldout" | "inactive"
if is_inactive:
    status_kind = "inactive"
    status_msg = "Indisponible"
elif is_out_of_stock:
    status_kind = "soldout"
    status_msg = "Rupture de stock"
elif is_closed:
    status_kind = "closed"
    status_msg = f"Commandes fermées — ouvre à {OPEN_TIME.strftime('%H:%M')}"


    return render(request, "shop/meal_of_day.html", {
        "meal": meal_of_day,
        "categories": categories,
        "variants": variants,
        "order_window_open": order_window_open,
        "service_day": service_day,
        "service_weekday": service_weekday,
        "open_time": OPEN_TIME,
        "cutoff_time": CUTOFF_TIME,
        "now": now,
        "next_open_dt": next_open_dt,
        "next_cutoff_dt": next_cutoff_dt,
        "sold_out": sold_out,
        "is_closed": is_closed,
        "is_out_of_stock": is_out_of_stock,
        "is_inactive": is_inactive,
        "status_kind": status_kind,
        "status_msg": status_msg,
    })
