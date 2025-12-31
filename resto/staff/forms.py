# staff/forms.py
from django import forms
from shop.models import Meal

class MealForm(forms.ModelForm):
    class Meta:
        model = Meal
        fields = ["category", "name", "slug", "description", "price", "stock", "is_active", "image"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }
