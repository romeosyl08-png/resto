from django import forms
from .models import UserProfile

class ProfileForm(forms.ModelForm):
    address = forms.CharField(
        label="Adresse / Lieu de livraison",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "readonly": "readonly"
        })
    )

    class Meta:
        model = UserProfile
        fields = ["customer_name", "phone", "address"]
