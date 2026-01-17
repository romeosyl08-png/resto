from django import forms
from django.forms import inlineformset_factory
from shop.models import Meal, MealVariant, WEEKDAY_CHOICES


class MealForm(forms.ModelForm):
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Jours disponibles",
    )

    class Meta:
        model = Meal
        fields = ["category", "name", "slug", "description", "stock", "is_active", "image"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "slug": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initial weekdays (si instance existante)
        if self.instance and self.instance.pk:
            current = self.instance.available_weekdays or []
            self.fields["weekdays"].initial = [str(x) for x in current]

    def clean_weekdays(self):
        # sécurise conversion + dédoublonnage
        raw = self.cleaned_data.get("weekdays") or []
        out = []
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return sorted(set(out))

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.available_weekdays = self.cleaned_data.get("weekdays") or []
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class MealVariantForm(forms.ModelForm):
    class Meta:
        model = MealVariant
        fields = ["code", "label", "price", "stock", "is_active"]
        widgets = {
            "code": forms.Select(attrs={"class": "form-select"}),
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


MealVariantFormSet = inlineformset_factory(
    parent_model=Meal,
    model=MealVariant,
    form=MealVariantForm,
    extra=3,
    can_delete=False,
    min_num=3,
    validate_min=True,
)
