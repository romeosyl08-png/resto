from django.shortcuts import render, get_object_or_404
from .models import Meal, Category
from django.shortcuts import render


def meal_list(request, category_slug=None):
    category = None
    categories = Category.objects.all()
    meals = Meal.objects.filter(is_active=True)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        meals = meals.filter(category=category)

    return render(request, 'shop/meal_list.html', {
        'category': category,
        'categories': categories,
        'meals': meals,
    })


def meal_detail(request, slug):
    meal = get_object_or_404(Meal, slug=slug, is_active=True)
    return render(request, 'shop/meal_detail.html', {'meal': meal})




from datetime import time
from django.utils import timezone
from django.shortcuts import render
from .models import Meal, Category

CUTOFF_TIME = time(14, 35)  # 08:30

def meal_llist(request, category_slug=None):
    now = timezone.localtime()
    sold_out = now.time() >= CUTOFF_TIME

    # 1) Plat du jour (simple)
    meal_of_day = Meal.objects.filter(is_active=True).order_by("-id").first()

    # si tu veux garder les catégories pour plus tard (optionnel)
    categories = Category.objects.all()

    return render(request, "shop/meal_of_day.html", {
        "meal": meal_of_day,
        "categories": categories,
        "sold_out": sold_out,
        "cutoff_time": CUTOFF_TIME,
        "now": now,
    })



