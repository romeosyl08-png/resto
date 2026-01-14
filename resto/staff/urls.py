from django.urls import path
from . import views

app_name = "staff"

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),

    path("order/<int:order_id>/confirmed/", views.mark_order_confirmed, name="mark_order_confirmed"),
    path("order/<int:order_id>/canceled/", views.mark_order_canceled, name="mark_order_canceled"),
    path("order/<int:order_id>/delivered/", views.mark_order_delivered, name="mark_order_delivered"),

    path("users/", views.admin_user_list, name="admin_user_list"),
    path("users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),

    path("meals/", views.meal_list, name="meal_list"),
    path("meals/new/", views.meal_create, name="meal_create"),
    path("meals/<int:meal_id>/edit/", views.meal_update, name="meal_update"),
    path("meals/<int:meal_id>/delete/", views.meal_delete, name="meal_delete"),
]
