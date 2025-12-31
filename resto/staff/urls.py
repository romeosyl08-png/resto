from django.urls import path
from . import views

app_name = "staff"

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("order/<int:order_id>/delivered/", views.mark_order_delivered, name="mark_order_delivered"),

    path("users/", views.admin_user_list, name="admin_user_list"),
    path("users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),
]
