from django.db import models
from django.utils.translation import gettext_lazy as _

WEEKDAY_CHOICES = [
    (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
    (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche"),
]

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Meal(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='meals')
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='meals/', blank=True, null=True)

    stock = models.PositiveIntegerField(default=0)  # stock global (optionnel)
    max_per_order = models.PositiveIntegerField(default=10)

    available_weekdays = models.JSONField(default=list, blank=True)  # ex: [0,2,4]

    def __str__(self):
        return self.name


class MealVariant(models.Model):
    class Code(models.TextChoices):
        BASIC = "basic", _("Basic")
        STANDARD = "standard", _("Standard")
        PREMIUM = "premium", _("Premium")

    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="variants")
    code = models.CharField(max_length=20, choices=Code.choices)
    label = models.CharField(max_length=50, blank=True)
    price = models.PositiveIntegerField()  # FCFA (int)
    stock = models.PositiveIntegerField(default=0)  # stock par tarif (recommandé)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("meal", "code")

    def __str__(self):
        return f"{self.meal.name} — {self.get_code_display()}"
