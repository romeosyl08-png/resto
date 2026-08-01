from django.urls import path
from . import views

app_name = "staff"

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),

    # Commandes - NOUVEAU
    path("orders/", views.admin_orders_list, name="admin_orders_list"),
    path("orders/<int:order_id>/", views.admin_order_detail, name="admin_order_detail"),
    
    path("order/<int:order_id>/confirmed/", views.mark_order_confirmed, name="mark_order_confirmed"),
    path("order/<int:order_id>/canceled/", views.mark_order_canceled, name="mark_order_canceled"),
    path("order/<int:order_id>/delivered/", views.mark_order_delivered, name="mark_order_delivered"),

    path("users/", views.admin_user_list, name="admin_user_list"),
    path("users/<int:user_id>/", views.admin_user_detail, name="admin_user_detail"),

    path("referrals/", views.referral_dashboard, name="referral_dashboard"),

    path("meals/", views.meal_list, name="meal_list"),
    path("meals/new/", views.meal_create, name="meal_create"),
    path("meals/<int:meal_id>/edit/", views.meal_update, name="meal_update"),
    path("meals/<int:meal_id>/delete/", views.meal_delete, name="meal_delete"),

    # Accounting Ledger
    path("accounting/", views.accounting_ledger, name="accounting_ledger"),
    path("accounting/expense/add/", views.add_expense, name="add_expense"),
    path("accounting/expense/<int:expense_id>/edit/", views.edit_expense, name="edit_expense"),
    path("accounting/expense/<int:expense_id>/delete/", views.delete_expense, name="delete_expense"),
    path("accounting/sale/add/", views.add_off_site_sale, name="add_off_site_sale"),
    path("accounting/sale/<int:sale_id>/edit/", views.edit_off_site_sale, name="edit_off_site_sale"),
    path("accounting/sale/<int:sale_id>/delete/", views.delete_off_site_sale, name="delete_off_site_sale"),
    
    # Debts
    path("accounting/debts/", views.debt_list, name="debt_list"),
    path("accounting/debts/add/", views.debt_create, name="debt_create"),
    path("accounting/debts/<int:debt_id>/", views.debt_detail, name="debt_detail"),
    path("accounting/debts/<int:debt_id>/edit/", views.debt_edit, name="debt_edit"),
    path("accounting/debts/<int:debt_id>/mark-paid/", views.debt_mark_paid, name="debt_mark_paid"),
    path("accounting/debts/<int:debt_id>/mark-unpaid/", views.debt_mark_unpaid, name="debt_mark_unpaid"),
    path("accounting/debts/<int:debt_id>/delete/", views.debt_delete, name="debt_delete"),
]
