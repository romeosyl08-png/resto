from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from shop.models import Product, Supplement

User = get_user_model()


class Expense(models.Model):
    """
    Modèle pour les dépenses fixes ou variables du restaurant.
    Peut être utilisé pour suivi des coûts journaliers, hebdomadaires, mensuels.

        ("rent", "Loyer"),
        ("utilities", "Services (eau, électricité, gaz)"),
        ("supplies", "Fournitures"),
        ("staff", "Salaires"),
        ("delivery", "Livraison"),
        ("other", "Autre"),
    """
    CATEGORY_CHOICES = [
        ("Transport", "Transport"),
        ("utilities", "Services (eau, électricité, gaz)"),
        ("supplies", "Fournitures"),
        ("staff", "Salaires"),
        ("delivery", "Livraison"),
        ("other", "Autre"),
    ]

    date = models.DateField(default=timezone.now)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"

    def __str__(self):
        return f"{self.get_category_display()} - {self.amount}€ ({self.date})"


class OffSiteSale(models.Model):
    """
    Modèle pour les ventes hors du site (livraison personnelle, cash, etc.)
    Peut contenir des plats et/ou des suppléments spécifiques
    """
    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255, help_text="Description de la vente")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ("cash", "Espèces"),
            ("card", "Carte"),
            ("transfer", "Virement"),
            ("other", "Autre"),
        ],
        default="cash"
    )
    notes = models.TextField(blank=True, default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Vente hors site"
        verbose_name_plural = "Ventes hors site"

    def __str__(self):
        return f"{self.description} - {self.amount}€ ({self.date})"


class OffSiteSaleproduct(models.Model):
    """
    Modèle intermédiaire pour associer des plats à une vente hors site avec quantité
    """
    off_site_sale = models.ForeignKey(
        OffSiteSale, 
        on_delete=models.CASCADE, 
        related_name="product_items"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Prix unitaire au moment de la vente"
    )

    class Meta:
        unique_together = ("off_site_sale", "product")
        verbose_name = "Plat de vente hors site"
        verbose_name_plural = "Plats de vente hors site"

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.price


class OffSiteSaleSupplement(models.Model):
    """
    Modèle intermédiaire pour associer des suppléments à une vente hors site avec quantité
    """
    off_site_sale = models.ForeignKey(
        OffSiteSale, 
        on_delete=models.CASCADE, 
        related_name="supplement_items"
    )
    supplement = models.ForeignKey(Supplement, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Prix unitaire au moment de la vente"
    )

    class Meta:
        unique_together = ("off_site_sale", "supplement")
        verbose_name = "Supplément de vente hors site"
        verbose_name_plural = "Suppléments de vente hors site"

    def __str__(self):
        return f"{self.supplement.name} x{self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.price


class Debt(models.Model):
    """
    Modèle pour gérer les dettes entre le restaurant et les utilisateurs.
    Un montant positif = l'utilisateur doit de l'argent au restaurant
    Un montant négatif = le restaurant doit de l'argent à l'utilisateur
    """
    DEBT_TYPE_CHOICES = [
        ("customer", "Client me doit"),
        ("supplier", "Je dois au fournisseur"),
        ("employee", "Je dois à l'employé"),
        ("other", "Autre"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="debts",
        null=True,
        blank=True,
        help_text="Utilisateur concerné (optionnel)"
    )
    
    debt_type = models.CharField(
        max_length=20,
        choices=DEBT_TYPE_CHOICES,
        default="customer"
    )
    
    description = models.CharField(max_length=255, help_text="Raison de la dette")
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Montant de la dette (positif ou négatif)"
    )
    
    reason = models.TextField(blank=True, default="", help_text="Détails supplémentaires")
    
    date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True, help_text="Date d'échéance")
    
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "Dette"
        verbose_name_plural = "Dettes"

    def __str__(self):
        status = "✓ Payée" if self.is_paid else "⚠ Non payée"
        user_info = f" ({self.user.username})" if self.user else ""
        return f"{self.description}{user_info} - {self.amount}€ [{status}]"

    @property
    def is_overdue(self):
        """Vérifie si la dette est en retard"""
        if self.is_paid or not self.due_date:
            return False
        return self.due_date < timezone.now().date()

    def mark_as_paid(self):
        """Marquer la dette comme payée"""
        self.is_paid = True
        self.paid_date = timezone.now().date()
        self.save()

    def mark_as_unpaid(self):
        """Annuler le paiement de la dette"""
        self.is_paid = False
        self.paid_date = None
        self.save()
