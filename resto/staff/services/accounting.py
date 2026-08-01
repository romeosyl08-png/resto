from decimal import Decimal
from django.db.models import Sum
from orders.models import Order
from staff.models import Expense, OffSiteSale


class AccountingService:

    @staticmethod
    def compute_period(start_date, end_date):
        site_orders = Order.objects.filter(
            created_at__date__range=(start_date, end_date),
            status="delivered"
        )

        site_revenue = site_orders.aggregate(
            total=Sum("total")
        )["total"] or Decimal("0")

        off_site_sales = OffSiteSale.objects.filter(
            date__range=(start_date, end_date)
        )

        off_site_revenue = off_site_sales.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        expenses = Expense.objects.filter(
            date__range=(start_date, end_date)
        )

        total_expenses = expenses.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")

        total_revenue = site_revenue + off_site_revenue
        result = total_revenue - total_expenses
        margin = (result / total_revenue * 100) if total_revenue else Decimal("0")

        return {
            "site_revenue": site_revenue,
            "off_site_revenue": off_site_revenue,
            "total_revenue": total_revenue,
            "total_expenses": total_expenses,
            "result": result,
            "margin_pct": margin
        }
