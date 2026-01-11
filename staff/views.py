from django.shortcuts import get_object_or_404, redirect, render
from orders.cart import Cart
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Sum, F ,Count
from django.utils import timezone
from orders.models import Order, OrderItem
from shop.models import Meal
from django.views.decorators.http import require_POST

from django.contrib import messages
from .forms import MealForm

from orders.loyalty import apply_loyalty_on_delivery  # import

from marketing.models import LoyaltyAccount, FreeItemVoucher

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
def admin_user_list(request):
    User = get_user_model()
    users = User.objects.order_by("-date_joined")[:200]
    return render(request, "admin/user_list.html", {"users": users})


@staff_member_required
def admin_user_detail(request, user_id: int):
    User = get_user_model()
    u = get_object_or_404(User, id=user_id)

    orders = Order.objects.filter(user=u).order_by("-created_at")[:50]
    counts = (
        Order.objects.filter(user=u)
        .values("status")
        .annotate(n=Count("id"))
    )
    counts_map = {x["status"]: x["n"] for x in counts}

    total_spent = Order.objects.filter(user=u, status="delivered").aggregate(s=Sum("total"))["s"] or 0

    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=u)
    
    vouchers_available = FreeItemVoucher.objects.filter(
        user=u,
        status=FreeItemVoucher.Status.AVAILABLE
    ).count()
    

    return render(request, "admin/user_detail.html", {
        "u": u,
        "orders": orders,
        "counts": counts_map,
        "total_spent": total_spent,
        "loyalty_points": getattr(loyalty, "stamps", 0),  # si ton champ s’appelle stamps
        "free_vouchers": vouchers_available,
    })


@staff_member_required
def meal_list(request):
    q = request.GET.get("q", "").strip()
    qs = Meal.objects.select_related("category").order_by("category__name", "name")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "admin/meals/meal_list.html", {"meals": qs, "q": q})

@staff_member_required
def meal_create(request):
    if request.method == "POST":
        form = MealForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Plat créé.")
            return redirect("staff:meal_list")
    else:
        form = MealForm()
    return render(request, "admin/meals/meal_form.html", {"form": form, "mode": "create"})

@staff_member_required
def meal_update(request, meal_id: int):
    meal = get_object_or_404(Meal, id=meal_id)
    if request.method == "POST":
        form = MealForm(request.POST, request.FILES, instance=meal)
        if form.is_valid():
            form.save()
            messages.success(request, "Plat modifié.")
            return redirect("staff:meal_list")
    else:
        form = MealForm(instance=meal)
    return render(request, "admin/meals/meal_form.html", {"form": form, "meal": meal, "mode": "edit"})

@staff_member_required
def meal_delete(request, meal_id: int):
    meal = get_object_or_404(Meal, id=meal_id)
    if request.method == "POST":
        meal.delete()
        messages.success(request, "Plat supprimé.")
        return redirect("staff:meal_list")
    return render(request, "admin/meals/meal_confirm_delete.html", {"meal": meal})

@staff_member_required
@require_POST
def mark_order_delivered(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    # garde-fou anti double comptage
    if order.status != "delivered":
        order.status = "delivered"
        order.save(update_fields=["status"])

        apply_loyalty_on_delivery(order)

    return redirect("staff:admin_dashboard")



