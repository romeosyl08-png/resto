from django import forms
from django.forms import inlineformset_factory
from shop.models import Meal, MealVariant, WEEKDAY_CHOICES

class MealForm(forms.ModelForm):
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Jours disponibles",
    )

    class Meta:
        model = Meal
        fields = ["category", "name", "slug", "description", "stock", "is_active", "image"]
        # si tu gardes stock global; sinon retire "stock"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["weekdays"].initial = [str(x) for x in (self.instance.available_weekdays or [])]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.available_weekdays = [int(x) for x in self.cleaned_data.get("weekdays", [])]
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
            "price": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(),
        }


MealVariantFormSet = inlineformset_factory(
    parent_model=Meal,
    model=MealVariant,
    form=MealVariantForm,
    extra=0,
    can_delete=False,
    min_num=3,
    validate_min=True,
)
