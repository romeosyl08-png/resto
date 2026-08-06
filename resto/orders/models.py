from decimal import Decimal
from django.conf import settings
from django.db import models
from shop.models import Product, Supplement



class Address(models.Model):
    ROOM_CHOICES = [
        ("L1", "Licence 1"),
        ("L2", "Licence 2"),
        ("L3", "Licence 3"),
        ("M1", "Master 1"),
        ("M2", "Master 2"),
    ]

    SECTOR_CHOICES = [
        ("EAI", "EAI"),
        ("EEM", "EEM"),
        ("IME", "IME"),
        ("IRST", "IRST"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses"
    )

    room = models.CharField(
        max_length=2,
        choices=ROOM_CHOICES,
        blank=True
    )

    sector = models.CharField(
        max_length=10,
        choices=SECTOR_CHOICES,
        blank=True
    )

    other = models.BooleanField(
        default=False,
        help_text="Adresse externe (livraison Yango/Glovo)"
    )

    other_detail = models.TextField(
        blank=True,
        help_text="Adresse exacte si autre endroit"
    )

    delivery_paid = models.BooleanField(
        default=False,
        help_text="Livraison payante"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.other:
            # Autre endroit → pas de room / sector
            if self.room or self.sector:
                raise ValidationError(
                    "Si 'autre endroit' est sélectionné, room et sector doivent être vides."
                )
            if not self.other_detail.strip():
                raise ValidationError(
                    "Veuillez préciser l’adresse exacte pour un autre endroit."
                )
        else:
            # Adresse interne → room + sector obligatoires
            if not self.room or not self.sector:
                raise ValidationError(
                    "Le niveau et la fillière sont obligatoires pour une adresse interne."
                )

    def __str__(self):
        if self.other:
            return f"Autre endroit – livraison payante"
        return f"{self.room} – {self.sector}"

    def save(self, *args, **kwargs):
        Address.objects.filter(user=self.user).exclude(pk=self.pk).delete()
        super().save(*args, **kwargs)
        
        from comptes.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.default_address = self
        profile.save(update_fields=["default_address"])





class Order(models.Model):
    STATUS_CHOICES = (
        ("pending", "En attente"),
        ("confirmed", "Confirmée"),
        ("canceled", "Annulée"),
        ("delivered", "Livrée"),
    )
 
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="orders",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    customer_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True, default="")
    address_detail = models.CharField(max_length=255, blank=True, default="")

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    promo_code = models.CharField(max_length=32, null=True, blank=True)
    loyalty_points_used = models.PositiveIntegerField(default=0)
    loyalty_reward = models.CharField(max_length=20, blank=True, default="")
    loyalty_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    is_delivered = models.BooleanField(default=False)
    counted_for_referral = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)


    # ✅ CODE CORRECT
    def recompute_subtotal(self):
        sub = Decimal("0.00")
        for item in self.items.all():
            sub += item.subtotal()  # Déjà inclut les suppléments !
        
        self.subtotal = sub
        self.total = max(Decimal("0.00"), sub - (self.discount_total or Decimal("0.00")))

    def is_editable(self):
        return self.status not in ("delivered", "canceled")

    def __str__(self):
        return f"Commande #{self.id} - {self.customer_name}"
    
    def is_eligible_for_loyalty(self):
        return self.status == "delivered"




class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant_code = models.CharField(max_length=20, default="standard")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        base = self.quantity * self.unit_price
        supplements_total = sum(
            s.subtotal() for s in self.supplements.all()
        )
        return base + supplements_total
    
    def __str__(self):
        return f"{self.product.name} ({self.variant_code}) x{self.quantity}"




class OrderItemSupplement(models.Model):
    order_item = models.ForeignKey(
        "OrderItem",
        on_delete=models.CASCADE,
        related_name="supplements",
    )
    supplement = models.ForeignKey(
        Supplement,
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantity * self.unit_price
    
    def __str__(self):
        return f"{self.supplement.name} x{self.quantity} pour {self.order_item.product.name}"
