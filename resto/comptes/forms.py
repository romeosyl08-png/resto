from django import forms
from .models import UserProfile
from orders.models import Address


class ProfileForm(forms.ModelForm):
    default_address = forms.ModelChoiceField(
        label="Adresse de livraison par défaut",
        queryset=Address.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = UserProfile
        fields = ["full_name", "phone", "default_address"]
        labels = {
            "full_name": "Nom complet",
            "phone": "Téléphone",
        }
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["default_address"].queryset = Address.objects.filter(user=user)


class AddressForm(forms.ModelForm):
    """Formulaire pour créer/modifier une adresse"""
    
    class Meta:
        model = Address
        fields = ['room', 'sector', 'other', 'other_detail']
        labels = {
            'room': 'Niveau',
            'sector': 'Filière',
            'other': 'Autre endroit (livraison payante)',
            'other_detail': 'Adresse exacte',
        }
        widgets = {
            'room': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_room'
            }),
            'sector': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_sector'
            }),
            'other': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_other'
            }),
            'other_detail': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse exacte pour Yango/Glovo',
                'id': 'id_other_detail'
            }),
        }
    
    def clean(self):
        cleaned = super().clean()
        other = cleaned.get('other')
        room = cleaned.get('room')
        sector = cleaned.get('sector')
        other_detail = (cleaned.get('other_detail') or '').strip()
        
        if other:
            # Si "autre endroit", room et sector doivent être vides
            if room or sector:
                raise forms.ValidationError(
                    "Si 'Autre endroit' est sélectionné, ne remplissez pas niveau ni Filière/Secteur."
                )
            if not other_detail:
                self.add_error('other_detail', "L'adresse exacte est obligatoire pour un autre endroit.")
        else:
            # Si adresse interne, room et sector sont obligatoires
            if not room:
                self.add_error('room', "Le niveau est obligatoire.")
            if not sector:
                self.add_error('sector', " Filière est obligatoire.")
        
        return cleaned