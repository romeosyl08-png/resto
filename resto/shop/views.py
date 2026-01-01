from django.shortcuts import render, get_object_or_404
from .models import Meal, Category
from django.shortcuts import render


# shop/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _

WEEKDAY_CHOICES = [
    (0, "Lundi"),
    (1, "Mardi"),
    (2, "Mercredi"),
    (3, "Jeudi"),
    (4, "Vendredi"),
    (5, "Samedi"),
    (6, "Dimanche"),
]

class Meal(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='meals')
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='meals/', blank=True, null=True)

    stock = models.PositiveIntegerField(default=0)

    available_weekdays = models.JSONField(default=list, blank=True)  # ex: [0,2,4]



def meal_detail(request, slug):
    meal = get_object_or_404(Meal, slug=slug, is_active=True)
    return render(request, 'shop/meal_detail.html', {'meal': meal})







