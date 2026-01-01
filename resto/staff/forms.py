# staff/forms.py
from django import forms
from shop.models import Meal, WEEKDAY_CHOICES

class MealForm(forms.ModelForm):
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Jours disponibles",
    )

    class Meta:
        model = Meal
        fields = ["category","name","slug","description","price","stock","is_active","image"]

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
