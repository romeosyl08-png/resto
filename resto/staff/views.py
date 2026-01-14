from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F, Count
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem
from shop.models import Meal
from .forms import MealForm

from marketing.models import LoyaltyAccount, FreeItemVoucher
from marketing.services import LoyaltyService


@staff_member_required
def admin_dashboard(request):
    """
    Dashboard staff : stats du jour (ou date demandée), dernières commandes, top plats.
    """
    # date sélectionnée (YYYY-MM-DD) sinon today
    date_str = request.GET.get("date")
    if date_str:
        try:
            day = timezone.datetime.fromisoformat(date_str).date()
        except Exception:
            day = timezone.localdate()
    else:
        day = timezone.localdate()

    orders_qs = (
        Order.objects
        .filter(created_at__date=day)
        .select_related("user")
        .order_by("-created_at")
    )

    orders_count = orders_qs.count()
    total_sales = orders_qs.aggregate(total=Sum("total"))["total"] or 0
    pending_count = Order.objects.filter(status="pending").count()

    top_meals = (
        OrderItem.objects
        .filter(order__created_at__date=day)
        .select_related("meal")
        .values("meal__name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price")),
        )
        .order_by("-quantity_sold")[:5]
    )

    meals = Meal.objects.select_related("category").order_by("category__name", "name")
    
    orders_today = (
    Order.objects
    .filter(created_at__date=today)
    .select_related("user")
    .prefetch_related("used_vouchers")
    )

    context = {
        "day": day,
        "orders_today": orders_qs[:50],
        "orders_count_today": orders_count,
        "total_sales_today": total_sales,
        "pending_orders_count": pending_count,
        "top_meals": top_meals,
        "meals": meals,
    }
    return render(request, "admin/dashboard.html", context)


@staff_member_required
def admin_user_list(request):
    User = get_user_model()
    q = request.GET.get("q", "").strip()

    users = User.objects.order_by("-date_joined")
    if q:
        users = users.filter(username__icontains=q) | users.filter(email__icontains=q)

    users = users[:200]
    return render(request, "admin/user_list.html", {"users": users, "q": q})


@staff_member_required
def admin_user_detail(request, user_id: int):
    User = get_user_model()
    u = get_object_or_404(User, id=user_id)

    orders = (
        Order.objects
        .filter(user=u)
        .prefetch_related("items", "used_vouchers")  # FreeItemVoucher.used_order related_name="used_vouchers"
        .order_by("-created_at")[:50]
    )

    counts = (
        Order.objects.filter(user=u)
        .values("status")
        .annotate(n=Count("id"))
    )
    counts_map = {x["status"]: x["n"] for x in counts}

    total_spent = (
        Order.objects
        .filter(user=u, status="delivered")
        .aggregate(s=Sum("total"))["s"] or 0
    )

    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=u)

    vouchers_available = (
        FreeItemVoucher.objects.filter(
            user=u,
            status=FreeItemVoucher.Status.AVAILABLE,
            expires_at__gt=timezone.now()
        ).count()
    )

    vouchers_list = (
        FreeItemVoucher.objects
        .filter(user=u)
        .order_by("-created_at")[:10]
    )

    next_free_in = (8 - (loyalty.stamps % 8)) if (loyalty.stamps % 8) != 0 else 0

    return render(request, "admin/user_detail.html", {
        "u": u,
        "orders": orders,
        "counts": {
            "pending": counts_map.get("pending", 0),
            "confirmed": counts_map.get("confirmed", 0),
            "delivered": counts_map.get("delivered", 0),
            "canceled": counts_map.get("canceled", 0),
        },
        "total_spent": total_spent,
        "loyalty_points": loyalty.stamps,
        "next_free_in": next_free_in,
        "free_vouchers": vouchers_available,
        "vouchers": vouchers_list,
    })


# -------- MEALS CRUD --------

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


# -------- ORDER STATUS ACTIONS --------

@staff_member_required
@require_POST
def mark_order_confirmed(request, order_id: int):
    order = get_object_or_404(Order, id=order_id)
    if order.status == "pending":
        order.status = "confirmed"
        order.save(update_fields=["status"])
        messages.success(request, f"Commande #{order.id} confirmée.")
    return redirect("staff:admin_dashboard")


@staff_member_required
@require_POST
def mark_order_canceled(request, order_id: int):
    order = get_object_or_404(Order, id=order_id)
    if order.status != "delivered":
        order.status = "canceled"
        order.save(update_fields=["status"])
        messages.success(request, f"Commande #{order.id} annulée.")
    return redirect("staff:admin_dashboard")


@staff_member_required
@require_POST
def mark_order_delivered(request, order_id: int):
    order = get_object_or_404(Order, id=order_id)

    # anti double comptage + fidélité en atomic
    if order.status == "delivered":
        return redirect("staff:admin_dashboard")

    with transaction.atomic():
        order.status = "delivered"
        order.save(update_fields=["status"])

        # fidélité : crée vouchers si seuil atteint
        LoyaltyService.on_order_delivered(order)

    messages.success(request, f"Commande #{order.id} livrée (fidélité appliquée).")
    return redirect("staff:admin_dashboard")
