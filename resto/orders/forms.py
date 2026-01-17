from django import forms

ADDRESS_CHOICES = [
    ("IMERTEL", "IMERTEL"),
    ("other", "Autre endroit (livraison via Yango/Glovo)"),
]

class CheckoutForm(forms.Form):
    customer_name = forms.CharField(
        label="Nom",
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Votre nom"})
    )

    phone = forms.CharField(
        label="Téléphone",
        max_length=10,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 0707070707"})
    )

    address = forms.ChoiceField(
        label="Zone de livraison",
        choices=ADDRESS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    address_detail = forms.CharField(
        label="Adresse exacte (si autre endroit)",
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ex : Rue X, immeuble Y, près de Z",
        })
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("address") == "other" and not (cleaned.get("address_detail") or "").strip():
            self.add_error("address_detail", "Veuillez préciser l’adresse exacte pour la livraison externe.")
        return cleaned
