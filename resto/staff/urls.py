from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
        # Dashboard + action pour marquer livré
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path(
        'admin/order/<int:order_id>/delivered/',
        views.mark_order_delivered,
        name='mark_order_delivered',
    ),
]