from django import forms
from comptes.models import UserProfile


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(label="Nom", max_length=150)
    phone = forms.CharField(label="Téléphone", max_length=30)
    address = forms.CharField(label="Adresse / Lieu de livraison", widget=forms.Textarea)