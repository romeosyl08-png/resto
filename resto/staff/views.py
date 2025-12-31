from django.shortcuts import get_object_or_404, redirect, render
from orders.cart import Cart
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, F
from django.utils import timezone
from orders.models import Order, OrderItem
from shop.models import Meal
from django.views.decorators.http import require_POST

from orders.loyalty import apply_loyalty_on_delivery  # import
# Create your views here.

@staff_member_required
def admin_dashboard(request):
    today = timezone.localdate()

    orders_today = Order.objects.filter(created_at__date=today)
    orders_count_today = orders_today.count()
    total_sales_today = orders_today.aggregate(total=Sum('total'))['total'] or 0

    pending_orders_count = Order.objects.filter(status='pending').count()

    top_meals = (
        OrderItem.objects
        .filter(order__created_at__date=today)
        .values('meal__name')
        .annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum(F('quantity') * F('unit_price')),
        )
        .order_by('-quantity_sold')[:5]
    )

    meals = Meal.objects.all().order_by('category__name', 'name')  # ← liste des plats

    context = {
        'today': today,
        'orders_count_today': orders_count_today,
        'total_sales_today': total_sales_today,
        'pending_orders_count': pending_orders_count,
        'top_meals': top_meals,
        'orders_today': orders_today,
        'meals': meals,  # ← on envoie au template
    }
    return render(request, 'admin/dashboard.html', context)







@staff_member_required
@require_POST
def mark_order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # garde-fou anti double comptage
    if order.status != "delivered":
        order.status = "delivered"
        order.save(update_fields=["status"])

        apply_loyalty_on_delivery(order)

    return redirect("admin_dashboard")



