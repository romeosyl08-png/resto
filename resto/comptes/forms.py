from django import forms
from .models import UserProfile

ADDRESS_CHOICES = [
    ("IMERTEL", "IMERTEL"),
    ("other", "Autre endroit (Yango/Glovo)"),
]

class ProfileForm(forms.ModelForm):
    address = forms.ChoiceField(
        label="Zone de livraison par défaut",
        choices=ADDRESS_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = UserProfile
        fields = ["full_name", "phone", "address"]
        labels = {"full_name": "Nom", "phone": "Téléphone"}
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }
