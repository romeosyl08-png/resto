from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


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
    max_per_order = models.PositiveIntegerField(default=10) 
    available_weekdays = models.JSONField(default=list, blank=True)  # ex: [0,2,4]










