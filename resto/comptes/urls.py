from django.urls import path, include
from . import views

app_name = 'comptes'

urlpatterns = [
    # Auth utilisateur (login / logout / password reset)
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('profile/', views.profile, name='profile'),
]