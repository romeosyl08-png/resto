from django.db import models
from django.urls import reverse
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

    stock = models.PositiveIntegerField(default=0)
    max_per_order = models.PositiveIntegerField(default=10)

    available_weekdays = models.JSONField(default=list, blank=True)

    supplements = models.ManyToManyField(
        "Supplement",
        blank=True,
        related_name="meals"
    )

    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('shop:meal_detail', args=[self.slug])



class MealVariant(models.Model):
    class Code(models.TextChoices):
        BASIC = "basic", _("Basic")
        STANDARD = "standard", _("Standard")
        PREMIUM = "premium", _("Premium")

    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="variants")
    code = models.CharField(max_length=20, choices=Code.choices)
    label = models.CharField(max_length=50, blank=True)
    price = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='meal_variants/', blank=True, null=True)

    supplements = models.ManyToManyField(
        "Supplement",
        blank=True,
        related_name="variants"
    )

    class Meta:
        unique_together = ("meal", "code")

    def __str__(self):
        return f"{self.meal.name} — {self.get_code_display()}"



class Supplement(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(
        max_length=50,
        default="Autre",
        help_text=_("Ex: Sauce, Boisson, Accompagnement"),
    )
    price = models.PositiveIntegerField()  # FCFA
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='meals/', blank=True, null=True)


    def __str__(self):
        return self.name
