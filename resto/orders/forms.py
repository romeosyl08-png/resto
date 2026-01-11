from django import forms
from comptes.models import UserProfile


class CheckoutForm(forms.ModelForm):
    customer_name = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Votre nom"
        })
    )
    phone = forms.CharField(
        label="Téléphone",
        max_length=10,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex: 0707070707"
        })
    )
    address = forms.CharField(
        label="Adresse / Lieu de livraison",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "readonly": "readonly",
        })
    )

    class Meta:
        model = UserProfile
        fields = ["customer_name", "phone", "address"]

