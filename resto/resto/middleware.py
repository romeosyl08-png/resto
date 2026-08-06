from django.shortcuts import redirect
from django.urls import reverse


class RestrictDjangoAdminMiddleware:
    """
    Autorise l'accès à /admin/ uniquement aux superusers.
    Les autres utilisateurs sont redirigés vers le menu public.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.menu_url = reverse("shop:product_list")
        self.admin_root = reverse("admin:index")

    def __call__(self, request):
        if request.path.startswith(self.admin_root):
            user = request.user
            if not (user.is_authenticated and user.is_superuser):
                return redirect(self.menu_url)
        return self.get_response(request)
