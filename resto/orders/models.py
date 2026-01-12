from decimal import Decimal
from django.conf import settings
from django.db import models
from shop.models import Meal


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

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    promo_code = models.CharField(max_length=32, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def recompute_subtotal(self):
        sub = Decimal("0.00")
        for item in self.items.all():
            sub += item.subtotal()
        self.subtotal = sub
        self.total = max(Decimal("0.00"), sub - (self.discount_total or Decimal("0.00")))

    def is_editable(self):
        return self.status not in ("delivered", "canceled")

    def __str__(self):
        return f"Commande #{self.id} - {self.customer_name}"



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    meal = models.ForeignKey(Meal, on_delete=models.PROTECT)
    variant_code = models.CharField(max_length=20, default="standard")  # <-- AJOUT
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # <-- un peu plus large

    def subtotal(self):
        return self.quantity * self.unit_price
