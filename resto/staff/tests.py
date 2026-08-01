from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from shop.models import Category, Meal, MealVariant
from staff.models import Debt


class StaffViewsRegressionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.manager_group, _ = Group.objects.get_or_create(name="Manager")

        self.manager = self.user_model.objects.create_user(
            username="manager",
            password="pass1234",
            is_staff=True,
        )
        self.manager.groups.add(self.manager_group)

        self.customer = self.user_model.objects.create_user(
            username="customer",
            password="pass1234",
        )

    def test_manager_required_redirects_to_comptes_login(self):
        response = self.client.get(reverse("staff:admin_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("comptes:login"), response.url)

    def test_add_expense_get_renders_without_runtime_error(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("staff:add_expense"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nouvelle Dépense")

    def test_orders_list_search_accepts_numeric_order_id(self):
        self.client.force_login(self.manager)

        order = Order.objects.create(
            user=self.customer,
            customer_name="Client Test",
            phone="0102030405",
            address="Campus",
            subtotal=Decimal("1500.00"),
            total=Decimal("1500.00"),
            status="pending",
        )

        response = self.client.get(reverse("staff:admin_orders_list"), {"search": str(order.id)})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Commande #{order.id}")

    def test_meal_list_renders_variant_price_range(self):
        self.client.force_login(self.manager)

        category = Category.objects.create(name="Plats", slug="plats")
        meal = Meal.objects.create(category=category, name="Riz", slug="riz")
        MealVariant.objects.create(meal=meal, code="basic", label="Basic", price=500, stock=10, is_active=True)
        MealVariant.objects.create(meal=meal, code="standard", label="Standard", price=1000, stock=10, is_active=True)

        response = self.client.get(reverse("staff:meal_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "500 - 1000 FCFA")

    def test_debt_pages_render(self):
        self.client.force_login(self.manager)

        debt = Debt.objects.create(
            user=self.customer,
            debt_type="customer",
            description="Achat à crédit",
            amount=Decimal("2000.00"),
        )

        list_response = self.client.get(reverse("staff:debt_list"))
        detail_response = self.client.get(reverse("staff:debt_detail", args=[debt.id]))

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Achat à crédit")
