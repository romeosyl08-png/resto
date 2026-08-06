from django.db import models
from django.conf import settings 



from comptes.utils import generate_referral_code

class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    default_address = models.OneToOneField(
        "orders.Address",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    referral_code = models.CharField(
        max_length=12,
        unique=True,
        null=True,
        blank=True
    )

    referred_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals"
    )

    free_products = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = generate_referral_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Profil de {self.user.username}"
