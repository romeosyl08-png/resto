from django.urls import path, include
from . import views

app_name = 'comptes'

urlpatterns = [
    # Auth utilisateur (login / logout / password reset)
    path('accounts/signup/', views.signup, name='signup'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('profile/', views.profile, name='profile'),

        # Gestion des adresses
    path("address/add/", views.add_address, name="add_address"),
    path("address/<int:address_id>/edit/", views.edit_address, name="edit_address"),
    path("address/<int:address_id>/delete/", views.delete_address, name="delete_address"),

]