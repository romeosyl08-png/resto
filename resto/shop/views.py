from django.shortcuts import render, get_object_or_404
from .models import Meal, Category
from django.shortcuts import render


def meal_detail(request, slug):
    meal = get_object_or_404(Meal, slug=slug, is_active=True)
    return render(request, 'shop/meal_detail.html', {'meal': meal})



# shop/views.py
from datetime import time, datetime, timedelta
from django.utils import timezone


OPEN_TIME = time(18, 0)
CUTOFF_TIME = time(9, 30)

def _is_order_window_open(now_time: time) -> bool:
    # ouvert de 18:00 → 23:59 et de 00:00 → 09:29
    return (now_time >= OPEN_TIME) or (now_time < CUTOFF_TIME)

def _service_date(now_dt):
    # après 18h → menu du lendemain
    return (now_dt.date() + timedelta(days=1)) if now_dt.time() >= OPEN_TIME else now_dt.date()

def meal_list(request, category_slug=None):
    now = timezone.localtime()
    order_window_open = _is_order_window_open(now.time())

    service_day = _service_date(now)
    service_weekday = service_day.weekday()  # 0=Mon ... 6=Sun

    # plats actifs (tu peux filtrer category_slug si tu veux)
    # shop/views.py
    qs = Meal.objects.filter(is_active=True)
    
    # si le champ n'existe pas en DB (prod pas migrée), on ignore le filtre jours
    try:
        qs = qs.values("id")  # force une requête simple
        Meal._meta.get_field("available_weekdays")
        has_weekdays = True
    except Exception:
        has_weekdays = False
    
    if has_weekdays:
        meals_today = [m for m in Meal.objects.filter(is_active=True).order_by("-id")
                       if service_weekday in (getattr(m, "available_weekdays", []) or [])]
    else:
        meals_today = list(Meal.objects.filter(is_active=True).order_by("-id"))



    meal_of_day = meals_today[0] if meals_today else None
    categories = Category.objects.all()

    # sold_out correct
    sold_out = True
    if meal_of_day:
        sold_out = (not order_window_open) or (meal_of_day.stock <= 0) or (not meal_of_day.is_active)

    # info prochaine ouverture (utile UI)
    # si commandes ouvertes -> prochaine fermeture = aujourd’hui à 09:30 (si matin) sinon demain 09:30
    # sinon prochaine ouverture = aujourd’hui 18:00 (si avant 18) sinon demain 18:00
    today = now.date()
    next_open_dt = timezone.make_aware(datetime.combine(today, OPEN_TIME))
    if now.time() >= OPEN_TIME:
        next_open_dt = timezone.make_aware(datetime.combine(today + timedelta(days=1), OPEN_TIME))
    if now.time() < OPEN_TIME:
        next_open_dt = timezone.make_aware(datetime.combine(today, OPEN_TIME))

    next_cutoff_dt = timezone.make_aware(datetime.combine(service_day, CUTOFF_TIME))

    return render(request, "shop/meal_of_day.html", {
        "meal": meal_of_day,
        "categories": categories,
        "sold_out": sold_out,
        "order_window_open": order_window_open,
        "service_day": service_day,
        "service_weekday": service_weekday,
        "open_time": OPEN_TIME,
        "cutoff_time": CUTOFF_TIME,
        "now": now,
        "next_open_dt": next_open_dt,
        "next_cutoff_dt": next_cutoff_dt,
    })




