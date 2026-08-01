from django import forms
from orders.models import Address

class CheckoutForm(forms.Form):
    customer_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if not phone.isdigit():
            raise forms.ValidationError("Le numéro doit contenir uniquement des chiffres.")
        if len(phone) != 10:
            raise forms.ValidationError("Le numéro doit contenir exactement 10 chiffres.")
        if not phone.startswith(('01', '05', '07')):
            raise forms.ValidationError("Le numéro doit commencer par 01, 05 ou 07.")
        return phone