from collections import OrderedDict
from django.shortcuts import render
from datetime import timedelta
# Create your views here.
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from itertools import groupby

from .models import Product, Category
from .utils import (
    WEEKDAYS,
    resolve_order_phase,
    service_date,
    OPEN_TIME,
    CUTOFF_TIME,
    sync_product_availability,
)
from .utils import ensure_product_variants
from .ui import ORDER_PHASE_UI



def weekly_menu(request):
    sync_product_availability()

    today = service_date(timezone.localtime())

    # dictionnaire ordonné jour → plats
    week_menu = OrderedDict()

    for offset in range(7):
        day = today + timedelta(days=offset)
        weekday = day.weekday()

        products = Product.objects.filter(
            is_active=True,
        ).order_by("-id")

        products_for_day = [
            product for product in products
            if weekday in (product.available_weekdays or [])
        ]

        if products_for_day:
            week_menu[weekday] = {
                "label": dict(WEEKDAYS)[weekday],
                "date": day,
                "products": products_for_day,
            }

    context = {
        "week_menu": week_menu,
    }

    return render(request, "shop/weekly_menu.html", context)



def _group_supplements_by_type(supplements):
    grouped = []
    for type_label, items in groupby(
        supplements, key=lambda s: (s.type or "Autre").strip() or "Autre"
    ):
        grouped.append({
            "label": type_label,
            "items": list(items),
        })
    return grouped


def product_list(request, category_slug=None):

    sync_product_availability()

    now = timezone.localtime()
    service_day = service_date(now)
    service_weekday = service_day.weekday()

    categories = Category.objects.all()

    qs = Product.objects.filter(is_active=True)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)

    # Produits disponibles aujourd’hui
    products_today = [
        product for product in qs.order_by("-id")
        if service_weekday in (product.available_weekdays or [])
    ]

    # ─────────────────────────────
    # CAS 1 : UN SEUL PLAT → MODE "PLAT DU JOUR"
    # ─────────────────────────────
    if len(products_today) == 1:
        product = products_today[0]

        # Création automatique des variantes
        if not product.variants.exists():
            ensure_product_variants(product)

        variants = list(product.variants.filter(is_active=True).order_by("price"))
        supplements = product.supplements.filter(is_active=True).order_by("type", "name")
        supplements_by_type = _group_supplements_by_type(supplements)

        phase = resolve_order_phase(
            now_time=now.time(),
            meal=product,
            variants=variants,
        )

        context = {
            "meal": product,
            "variants": variants,
            "supplements": supplements,
            "supplements_by_type": supplements_by_type,
            "phase": phase,
            "ui": ORDER_PHASE_UI[phase],
            "open_time": OPEN_TIME,
            "cutoff_time": CUTOFF_TIME,
            "categories": categories,
            "category": category_slug,
        }

        return render(request, "shop/meal_of_day.html", context)

    # ─────────────────────────────
    # CAS 2 : PLUSIEURS PLATS → MODE "MENU"
    # ─────────────────────────────
    context = {
        "meals": products_today,
        "categories": categories,
        "category": category_slug,
    }

    return render(request, "shop/meal_of_day.html", context)


    





def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    # Variantes automatiques si inexistantes
    if not product.variants.exists():
        ensure_product_variants(product)


    variants = product.variants.filter(is_active=True).order_by("price")
    supplements = product.supplements.filter(is_active=True).order_by("type", "name")
    supplements_by_type = _group_supplements_by_type(supplements)

    phase = resolve_order_phase(
        now_time=timezone.localtime().time(),
        product=product,
        variants=variants,
    )

    context = {
        "product": product,
        "variants": variants,
        "supplements": supplements,
        "supplements_by_type": supplements_by_type,
        "phase": phase,
        "ui": ORDER_PHASE_UI[phase],
        "open_time": OPEN_TIME,
        "cutoff_time": CUTOFF_TIME,
    }

    return render(request, "shop/meal_of_day.html", context)
