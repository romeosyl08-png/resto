from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from shop.models import Product, ProductVariant, WEEKDAY_CHOICES, Supplement
from .models import Expense, OffSiteSale, OffSiteSaleproduct, OffSiteSaleSupplement, Debt

User = get_user_model()




class ProductForm(forms.ModelForm):
    weekdays = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        required=False,
        label="Jours disponibles",
    )

    class Meta:
        model = Product
        fields = ["category", "name", "slug", "description", "stock", "is_active", "image"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-control", "id": "id_name"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "id": "id_slug"}),
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


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ["code", "label", "price", "stock", "is_active"]
        widgets = {
            "code": forms.Select(attrs={"class": "form-select"}),
            "label": forms.TextInput(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


ProductVariantFormSet = inlineformset_factory(
    parent_model=Product,
    model=ProductVariant,
    form=ProductVariantForm,

    extra=1,           # UNE seule variante vide par défaut
    can_delete=True,    # possibilité de supprimer
    min_num=0,          # aucune variante minimum obligatoire
    validate_min=False, # pas de validation minimum
)


# -------- ACCOUNTING FORMS --------

class ExpenseForm(forms.ModelForm):
    """Formulaire pour ajouter une dépense"""
    class Meta:
        model = Expense
        fields = ["date", "category", "description", "amount", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Achat de légumes",
            }),
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Notes (optionnel)",
            }),
        }


class OffSiteSaleForm(forms.ModelForm):
    """Formulaire pour ajouter une vente hors du site"""
    class Meta:
        model = OffSiteSale
        fields = ["date", "description", "amount", "payment_method", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "description": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Vente directe café",
            }),
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Notes (optionnel)",
            }),
        }


class OffSiteSaleproductForm(forms.ModelForm):
    """Formulaire pour ajouter un plat à une vente hors site"""
    class Meta:
        model = OffSiteSaleproduct
        fields = ["product", "quantity", "price"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "value": "1",
            }),
            "price": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }),
        }


class OffSiteSaleSupplementForm(forms.ModelForm):
    """Formulaire pour ajouter un supplément à une vente hors site"""
    class Meta:
        model = OffSiteSaleSupplement
        fields = ["supplement", "quantity", "price"]
        widgets = {
            "supplement": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "value": "1",
            }),
            "price": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }),
        }


# FormSets pour gérer les plats et suppléments d'une vente hors site
OffSiteSaleproductFormSet = inlineformset_factory(
    parent_model=OffSiteSale,
    model=OffSiteSaleproduct,
    form=OffSiteSaleproductForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

OffSiteSaleSupplementFormSet = inlineformset_factory(
    parent_model=OffSiteSale,
    model=OffSiteSaleSupplement,
    form=OffSiteSaleSupplementForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)

# -------- DEBT FORMS --------

class DebtForm(forms.ModelForm):
    """Formulaire pour créer/modifier une dette"""
    class Meta:
        model = Debt
        fields = ["user", "debt_type", "description", "amount", "reason", "date", "due_date", "is_paid"]
        widgets = {
            "user": forms.Select(attrs={
                "class": "form-select",
            }),
            "debt_type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ex: Vente à crédit",
            }),
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "placeholder": "0.00",
            }),
            "reason": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Détails supplémentaires (optionnel)",
            }),
            "date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "due_date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-control",
            }),
            "is_paid": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def save(self, commit=True):
        debt = super().save(commit=False)
        if debt.is_paid and not debt.paid_date:
            debt.paid_date = timezone.localdate()
        if not debt.is_paid:
            debt.paid_date = None
        if commit:
            debt.save()
            self.save_m2m()
        return debt
 