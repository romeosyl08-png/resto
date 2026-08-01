from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse_lazy


def is_manager(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="Manager").exists()
    )


def manager_required(view_func):
    """
    Autorise uniquement les managers (groupe Manager) et superusers.
    Redirige vers la page de connexion comptes.
    """
    return user_passes_test(
        is_manager,
        login_url=reverse_lazy("comptes:login"),
    )(view_func)
