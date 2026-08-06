import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem
from orders.utils import products_by_price
from comptes.models import UserProfile
from .utils import manager_required
from shop.models import Product, ProductVariant
from .forms import ProductForm, ProductVariantFormSet, ExpenseForm, OffSiteSaleForm, DebtForm
from .models import Expense, OffSiteSale, Debt

from marketing.models import LoyaltyAccount
from marketing.services import LoyaltyService

logger = logging.getLogger(__name__)

ALLOWED_STATUS_TRANSITIONS = {
    "pending": {"confirmed", "delivered", "canceled"},
    "confirmed": {"delivered", "canceled"},
    "delivered": set(),
    "canceled": set(),
}


def _transition_order_status(*, order_id: int, target: str):
    """
    Transitionne une commande de manière atomique avec verrouillage.
    Retourne (order, changed, reason).
    """
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), id=order_id)
        current = order.status

        if current == target:
            return order, False, "UNCHANGED"

        if target not in ALLOWED_STATUS_TRANSITIONS.get(current, set()):
            return order, False, "INVALID"

        order.status = target
        order.is_delivered = (target == "delivered")
        order.save(update_fields=["status", "is_delivered"])
        return order, True, "OK"


def _parse_date_param(raw_value: str | None):
    if not raw_value:
        return None
    try:
        return timezone.datetime.fromisoformat(raw_value).date()
    except ValueError:
        return None


def _is_safe_next_url(request, next_url: str | None) -> bool:
    if not next_url:
        return False
    if not (
        next_url.startswith("/")
        or next_url.startswith("http://")
        or next_url.startswith("https://")
    ):
        return False
    return url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )


def _resolve_next_url(request, fallback_url_name: str) -> str:
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER")
    )
    if _is_safe_next_url(request, next_url):
        return next_url
    return reverse(fallback_url_name)


@manager_required
def admin_dashboard(request):
    """
    Dashboard staff : stats du jour (ou date demandée), dernières commandes, top plats.
    """
    # date sélectionnée (YYYY-MM-DD) sinon today
    today = _parse_date_param(request.GET.get("date")) or timezone.localdate()

    orders_qs = (
        Order.objects
        .filter(created_at__date=today)
        .select_related("user")
        .order_by("-created_at")
    )

    orders_count = orders_qs.count()
    total_sales = orders_qs.aggregate(total=Sum("total"))["total"] or 0
    pending_count = orders_qs.filter(status="pending").count()

    top_products = (
        OrderItem.objects
        .filter(order__created_at__date=today)
        .select_related("product")
        .values("product__name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum(F("quantity") * F("unit_price")),
        )
        .order_by("-quantity_sold")[:5]
    )

    active_variants = Prefetch(
        "variants",
        queryset=ProductVariant.objects.filter(is_active=True).only("product_id", "price").order_by("price"),
    )
    products = (
        Product.objects
        .select_related("category")
        .prefetch_related(active_variants)
        .order_by("category__name", "name")
    )

    for product in products:
        prices = [v.price for v in product.variants.all()]
        product.price_min = min(prices) if prices else None
        product.price_max = max(prices) if prices else None

    context = {
        "today": today,
        "orders_today": orders_qs[:50],
        "orders_count_today": orders_count,
        "total_sales_today": total_sales,
        "pending_orders_count": pending_count,
        "top_products": top_products,
        "products": products,
    }
    return render(request, "admin/dashboard.html", context)


@manager_required
def admin_orders_list(request):
    """
    Page dédiée aux commandes avec tous les détails : 
    user, items, variants, supplements, prix, quantités
    """
    # Filtres
    status_filter = [s for s in request.GET.getlist("status") if s]
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    search = request.GET.get("search", "").strip()
    
    # QuerySet de base avec optimisation
    orders = (
        Order.objects
        .select_related("user")
        .prefetch_related(
            "items__product__category",
            "items__supplements__supplement"
        )
        .order_by("-created_at")
    )
    
    # Filtrage par statut
    if status_filter:
        orders = orders.filter(status__in=status_filter)

    
    # Filtrage par date
    if date_from:
        parsed_from = _parse_date_param(date_from)
        if parsed_from:
            orders = orders.filter(created_at__date__gte=parsed_from)
    
    if date_to:
        parsed_to = _parse_date_param(date_to)
        if parsed_to:
            orders = orders.filter(created_at__date__lte=parsed_to)
    
    # Recherche
    if search:
        search_filter = (
            Q(customer_name__icontains=search)
            | Q(phone__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
            | Q(promo_code__icontains=search)
        )
        if search.isdigit():
            search_filter |= Q(id=int(search))
        orders = orders.filter(search_filter)
    
    # Stats pour la page
    stats = {
        "total_count": orders.count(),
        "total_revenue": orders.aggregate(sum=Sum("total"))["sum"] or 0,
        "pending_count": orders.filter(status="pending").count(),
        "confirmed_count": orders.filter(status="confirmed").count(),
        "delivered_count": orders.filter(status="delivered").count(),
        "canceled_count": orders.filter(status="canceled").count(),
    }
    
    # Pagination
    paginator = Paginator(orders, 20)  # 20 commandes par page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    pagination_query = query_params.urlencode()

    context = {
        "page_obj": page_obj,
        "orders": page_obj.object_list,
        "stats": stats,
        "status_filter": status_filter,
        "date_from": date_from,
        "date_to": date_to,
        "search": search,
        "status_choices": Order.STATUS_CHOICES,
        "pagination_query": f"&{pagination_query}" if pagination_query else "",
    }
    
    return render(request, "admin/orders/orders_list.html", context)


@manager_required
def admin_order_detail(request, order_id: int):
    """
    Page de détail d'une commande spécifique avec toutes les informations
    """
    order = get_object_or_404(
        Order.objects
        .select_related("user")
        .prefetch_related(
            "items__product__category",
            "items__supplements__supplement"
        ),
        id=order_id
    )
    
    # Historique des commandes de ce client
    if order.user:
        user_orders = (
            Order.objects
            .filter(user=order.user)
            .exclude(id=order.id)
            .order_by("-created_at")[:5]
        )
        
        user_stats = {
            "total_orders": Order.objects.filter(user=order.user).count(),
            "total_spent": Order.objects.filter(
                user=order.user, 
                status="delivered"
            ).aggregate(sum=Sum("total"))["sum"] or 0,
        }
    else:
        user_orders = []
        user_stats = None
    
    context = {
        "order": order,
        "user_orders": user_orders,
        "user_stats": user_stats,
    }
    
    return render(request, "admin/orders/order_detail.html", context)


@manager_required
def admin_user_list(request):
    User = get_user_model()
    q = request.GET.get("q", "").strip()

    users_qs = User.objects.order_by("-date_joined")
    if q:
        users_qs = users_qs.filter(
            Q(username__icontains=q) | Q(email__icontains=q)
        )

    total_count = users_qs.count()
    users = list(users_qs[:200])
    staff_count = sum(1 for u in users if u.is_staff)
    last_signup = users[0].date_joined if users else None

    return render(request, "admin/users/user_list.html", {
        "users": users,
        "q": q,
        "total_count": total_count,
        "staff_count": staff_count,
        "last_signup": last_signup,
    })


@manager_required
def admin_user_detail(request, user_id: int):
    User = get_user_model()
    u = get_object_or_404(User, id=user_id)

    # Dernières commandes
    orders = (
        Order.objects
        .filter(user=u)
        .prefetch_related("items")
        .order_by("-created_at")[:50]
    )

    # Compteurs par statut
    counts = (
        Order.objects
        .filter(user=u)
        .values("status")
        .annotate(n=Count("id"))
    )
    counts_map = {x["status"]: x["n"] for x in counts}

    # Total dépensé
    total_spent = (
        Order.objects
        .filter(user=u, status="delivered")
        .aggregate(s=Sum("total"))["s"] or 0
    )

    # Fidélité (points)
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=u)
    loyalty.recompute()

    points = int(loyalty.points or 0)
    points_to_discount = max(0, 10 - points)
    points_to_free = max(0, 15 - points)

    def pct(val: int, total: int) -> int:
        if total <= 0:
            return 0
        return int(min(100, (val / total) * 100))

    p10_pct = pct(min(points, 10), 10)
    p15_pct = pct(min(points, 15), 15)


    stats = products_by_price(u)

    

    return render(request, "admin/users/user_detail.html", {
        "u": u,
        "orders": orders,

        # Statuts commandes
        "counts": {
            "pending": counts_map.get("pending", 0),
            "confirmed": counts_map.get("confirmed", 0),
            "delivered": counts_map.get("delivered", 0),
            "canceled": counts_map.get("canceled", 0),
        },

        # Dépenses
        "total_spent": total_spent,

        # Fidélité — points
        "points": points,
        "points_to_discount": points_to_discount,
        "points_to_free": points_to_free,
        "p10_pct": p10_pct,
        "p15_pct": p15_pct,

        **stats,
    })


# -------- productS CRUD --------

@manager_required
def product_list(request):
    q = request.GET.get("q", "").strip()
    active_variants = Prefetch(
        "variants",
        queryset=ProductVariant.objects.filter(is_active=True).only("product_id", "price").order_by("price"),
    )
    qs = (
        Product.objects
        .select_related("category")
        .prefetch_related(active_variants)
        .order_by("category__name", "name")
    )
    if q:
        qs = qs.filter(name__icontains=q)
    products = list(qs)
    for product in products:
        prices = [variant.price for variant in product.variants.all()]
        product.price_min = min(prices) if prices else None
        product.price_max = max(prices) if prices else None
    return render(request, "admin/products/product_list.html", {"products": products, "q": q})


@manager_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        variant_formset = ProductVariantFormSet(request.POST)
        if form.is_valid() and variant_formset.is_valid():
            with transaction.atomic():
                product = form.save()
                variant_formset.instance = product
                variant_formset.save()
                messages.success(request, "Plat créé.")
                return redirect("staff:product_list")
    else:
        form = ProductForm()
        variant_formset = ProductVariantFormSet(queryset=ProductVariant.objects.none())

    return render(request, "admin/products/product_form.html", {
        "form": form,
        "variant_formset": variant_formset,
        "mode": "create",
    })


@manager_required
def product_update(request, product_id: int):
    product = get_object_or_404(product, id=product_id)

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, instance=product)
        variant_formset = ProductVariantFormSet(request.POST, instance=product)

        if form.is_valid() and variant_formset.is_valid():
            with transaction.atomic():
                product = form.save()
                variant_formset.save()
                messages.success(request, "Plat modifié.")
                return redirect("staff:product_list")
    else:
        form = ProductForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product)

    context = {
        "form": form,
        "variant_formset": variant_formset,
        "product": product,
        "mode": "edit",
    }
    return render(request, "admin/products/product_form.html", context)


@manager_required
def product_delete(request, product_id: int):
    product = get_object_or_404(product, id=product_id)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Plat supprimé.")
        return redirect("staff:product_list")
    return render(request, "admin/products/product_confirm_delete.html", {"product": product})


# -------- ORDER STATUS ACTIONS --------

@staff_member_required
@require_POST
def mark_order_confirmed(request, order_id: int):
    order, changed, reason = _transition_order_status(
        order_id=order_id,
        target="confirmed",
    )

    if changed:
        messages.success(request, f"Commande #{order.id} confirmée.")
        logger.info("order_status_changed", extra={
            "order_id": order.id,
            "status": "confirmed",
            "actor_id": request.user.id,
        })
    elif reason == "INVALID":
        messages.warning(request, "Transition invalide: la commande ne peut pas être confirmée.")
    
    # Redirection intelligente
    return redirect(_resolve_next_url(request, "staff:admin_dashboard"))


@staff_member_required
@require_POST
def mark_order_canceled(request, order_id: int):
    order, changed, reason = _transition_order_status(
        order_id=order_id,
        target="canceled",
    )

    if changed:
        messages.success(request, f"Commande #{order.id} annulée.")
        logger.info("order_status_changed", extra={
            "order_id": order.id,
            "status": "canceled",
            "actor_id": request.user.id,
        })
    elif reason == "INVALID":
        messages.warning(request, "Transition invalide: la commande ne peut pas être annulée.")
    
    return redirect(_resolve_next_url(request, "staff:admin_dashboard"))


@staff_member_required
@require_POST
def mark_order_delivered(request, order_id: int):
    with transaction.atomic():
        order, changed, reason = _transition_order_status(
            order_id=order_id,
            target="delivered",
        )

        if changed:
            LoyaltyService.on_order_delivered(order)

    if changed:
        messages.success(request, f"Commande #{order.id} livrée (fidélité appliquée).")
        logger.info("order_status_changed", extra={
            "order_id": order.id,
            "status": "delivered",
            "actor_id": request.user.id,
        })
    elif reason == "INVALID":
        messages.warning(request, "Transition invalide: la commande ne peut pas être livrée.")
    
    return redirect(_resolve_next_url(request, "staff:admin_dashboard"))


# admin/views.py (ou staff/views.py)




@manager_required
def referral_dashboard(request):
    sponsors = (
        UserProfile.objects
        .filter(referrals__isnull=False)
        .annotate(
            total_referrals=Count("referrals", distinct=True),
            delivered_referrals=Count(
                "referrals__user__orders",
                filter=Q(
                    referrals__user__orders__status="delivered",
                    referrals__user__orders__counted_for_referral=True,
                ),
                distinct=True
            )
        )
        .select_related("user")
        .order_by("-delivered_referrals")
    )

    sponsors = list(sponsors)
    stats = {
        "sponsors_count": len(sponsors),
        "total_referrals": sum(s.total_referrals for s in sponsors),
        "delivered_referrals": sum(s.delivered_referrals for s in sponsors),
        "free_products": sum(s.free_products for s in sponsors),
    }

    return render(request, "admin/referral_dashboard.html", {
        "sponsors": sponsors,
        "stats": stats,
    })


# -------- ACCOUNTING LEDGER --------

def _get_accounting_data(date_obj):
    """
    Récupère toutes les données comptables pour une date donnée:
    - Commandes du jour
    - Ventes hors site du jour
    - Dépenses du jour
    Retourne un dictionnaire avec tous les résultats et totaux
    """
    # Commandes du jour (site)
    site_orders = Order.objects.filter(
        created_at__date=date_obj,
        status="delivered"
    )
    site_revenue = site_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    site_orders_count = site_orders.count()
    
    # Ventes hors site du jour
    off_site_sales = OffSiteSale.objects.filter(date=date_obj)
    off_site_revenue = off_site_sales.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    off_site_sales_count = off_site_sales.count()
    
    # Total revenus
    total_revenue = site_revenue + off_site_revenue
    
    # Dépenses du jour
    expenses = Expense.objects.filter(date=date_obj)
    total_expenses = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    
    # Résultat
    result = total_revenue - total_expenses
    
    return {
        "date": date_obj,
        "site_orders": site_orders,
        "site_revenue": site_revenue,
        "site_orders_count": site_orders_count,
        "off_site_sales": off_site_sales,
        "off_site_revenue": off_site_revenue,
        "off_site_sales_count": off_site_sales_count,
        "total_revenue": total_revenue,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "result": result,
    }


@staff_member_required
def accounting_ledger(request):
    """
    Livre de compte: vue des revenus, dépenses et résultats par jour, semaine, mois.
    S'inspire de admin_order_detail avec agrégation sur périodes.
    """
    period = request.GET.get("period", "day")
    ref_date = _parse_date_param(request.GET.get("date")) or timezone.localdate()

    custom_start = _parse_date_param(request.GET.get("start_date"))
    custom_end = _parse_date_param(request.GET.get("end_date"))

    if period == "custom" and custom_start and custom_end:
        if custom_start > custom_end:
            custom_start, custom_end = custom_end, custom_start
        start_date = custom_start
        end_date = custom_end
        period_label = f"Période du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
    elif period == "week":
        start_date = ref_date - timedelta(days=ref_date.weekday())
        end_date = start_date + timedelta(days=6)
        period_label = f"Semaine du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
    elif period == "month":
        start_date = ref_date.replace(day=1)
        if ref_date.month == 12:
            end_date = ref_date.replace(year=ref_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = ref_date.replace(month=ref_date.month + 1, day=1) - timedelta(days=1)
        period_label = f"Mois de {start_date.strftime('%B %Y')}"
    else:
        period = "day"
        start_date = ref_date
        end_date = ref_date
        period_label = f"Jour du {ref_date.strftime('%d/%m/%Y')}"
    
    # Aggrégation pour la période
    site_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status="delivered"
    )
    site_revenue = site_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    site_orders_count = site_orders.count()
    
    off_site_sales = OffSiteSale.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    )
    off_site_revenue = off_site_sales.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    off_site_sales_count = off_site_sales.count()
    
    total_revenue = site_revenue + off_site_revenue
    
    expenses = Expense.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).order_by("-date")
    total_expenses = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    
    result = total_revenue - total_expenses
    
    # Détails par jour (si jour sélectionné, sinon par jour pour la semaine/mois)
    daily_details = []
    if period == "day":
        # Un seul jour
        daily_details = [_get_accounting_data(ref_date)]
    else:
        # Tous les jours de la période
        current = start_date
        while current <= end_date:
            daily_details.append(_get_accounting_data(current))
            current += timedelta(days=1)
    
    # Dépenses par catégorie
    expenses_by_category_qs = (
        Expense.objects
        .filter(date__gte=start_date, date__lte=end_date)
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    expense_category_labels = dict(Expense.CATEGORY_CHOICES)
    expenses_by_category = [
        {
            **row,
            "label": expense_category_labels.get(row["category"], row["category"]),
        }
        for row in expenses_by_category_qs
    ]
    
    context = {
        "period": period,
        "period_label": period_label,
        "ref_date": ref_date,
        "start_date": start_date,
        "end_date": end_date,
        
        # Totaux
        "site_revenue": site_revenue,
        "site_orders_count": site_orders_count,
        "off_site_revenue": off_site_revenue,
        "off_site_sales_count": off_site_sales_count,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "result": result,
        "margin_pct": (result / total_revenue * 100) if total_revenue > 0 else 0,
        
        # Détails
        "daily_details": daily_details,
        "expenses": expenses[:20],  # Dernières dépenses
        "expenses_by_category": expenses_by_category,
        "off_site_sales": off_site_sales.order_by("-date")[:20],
        "current_path": request.get_full_path(),
    }
    
    return render(request, "admin/accounting/ledger.html", context)


@staff_member_required
def add_expense(request):
    """Page pour ajouter une dépense"""
    next_url = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST":
        form = ExpenseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Dépense ajoutée.")
            return redirect(_resolve_next_url(request, "staff:accounting_ledger"))
    else:
        form = ExpenseForm()

    context = {
        "form": form,
        "title": "Ajouter Dépense",
        "heading": "Nouvelle Dépense",
        "subtitle": "Enregistrement comptable",
        "icon": "bi-cash-coin",
        "submit_class": "btn-primary",
        "submit_label": "Enregistrer",
        "next": next_url if _is_safe_next_url(request, next_url) else "",
        "back_url": next_url if _is_safe_next_url(request, next_url) else reverse("staff:accounting_ledger"),
    }
    return render(request, "admin/accounting/add_expense.html", context)



@staff_member_required
def edit_expense(request, expense_id: int):
    """Page pour éditer une dépense"""
    expense = get_object_or_404(Expense, id=expense_id)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    
    if request.method == "POST":
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Dépense modifiée.")
            return redirect(_resolve_next_url(request, "staff:accounting_ledger"))

    else:
        form = ExpenseForm(instance=expense)

    context = {
        "form": form,
        "expense": expense,
        "mode": "edit",
        "title": "Modifier Dépense",
        "heading": "Modifier Dépense",
        "subtitle": "Mise à jour comptable",
        "icon": "bi-pencil-square",
        "submit_class": "btn-success",
        "submit_label": "Mettre à jour",
        "next": next_url if _is_safe_next_url(request, next_url) else "",
        "back_url": next_url if _is_safe_next_url(request, next_url) else reverse("staff:accounting_ledger"),
        "delete_url": reverse("staff:delete_expense", args=[expense.id]),
    }
    return render(request, "admin/accounting/add_expense.html", context)


@staff_member_required
@require_POST
def delete_expense(request, expense_id: int):
    """Supprime une dépense"""
    expense = get_object_or_404(Expense, id=expense_id)
    expense.delete()
    messages.success(request, "Dépense supprimée.")
    return redirect(_resolve_next_url(request, "staff:accounting_ledger"))


@staff_member_required
def add_off_site_sale(request):
    """Page pour ajouter une vente hors site"""
    next_url = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST":
        form = OffSiteSaleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Vente hors site ajoutée.")
            return redirect(_resolve_next_url(request, "staff:accounting_ledger"))
    else:
        form = OffSiteSaleForm()

    return render(request, "admin/accounting/add_off_site_sale.html", {
        "form": form,
        "next": next_url if _is_safe_next_url(request, next_url) else "",
        "back_url": next_url if _is_safe_next_url(request, next_url) else reverse("staff:accounting_ledger"),
    })


@staff_member_required
def edit_off_site_sale(request, sale_id: int):
    """Page pour éditer une vente hors site"""
    sale = get_object_or_404(OffSiteSale, id=sale_id)
    next_url = request.POST.get("next") or request.GET.get("next", "")
    
    if request.method == "POST":
        form = OffSiteSaleForm(request.POST, instance=sale)
        if form.is_valid():
            form.save()
            messages.success(request, "Vente hors site modifiée.")
            return redirect(_resolve_next_url(request, "staff:accounting_ledger"))

    else:
        form = OffSiteSaleForm(instance=sale)
    
    return render(request, "admin/accounting/add_off_site_sale.html", {
        "form": form,
        "sale": sale,
        "mode": "edit",
        "next": next_url if _is_safe_next_url(request, next_url) else "",
        "back_url": next_url if _is_safe_next_url(request, next_url) else reverse("staff:accounting_ledger"),
    })


@staff_member_required
@require_POST
def delete_off_site_sale(request, sale_id: int):
    """Supprime une vente hors site"""
    sale = get_object_or_404(OffSiteSale, id=sale_id)
    sale.delete()
    messages.success(request, "Vente hors site supprimée.")
    return redirect(_resolve_next_url(request, "staff:accounting_ledger"))

# -------- DEBT MANAGEMENT --------

@manager_required
def debt_list(request):
    """Liste des dettes avec filtres"""
    # Filtres
    status = request.GET.get("status", "")  # "paid", "unpaid", "overdue"
    user_id = request.GET.get("user_id", "")
    debt_type = request.GET.get("debt_type", "")
    search = request.GET.get("search", "").strip()
    
    # QuerySet de base
    debts = Debt.objects.select_related("user").order_by("-date", "-created_at")
    
    # Filtrer par statut
    if status == "paid":
        debts = debts.filter(is_paid=True)
    elif status == "unpaid":
        debts = debts.filter(is_paid=False)
    elif status == "overdue":
        debts = debts.filter(
            is_paid=False,
            due_date__isnull=False,
            due_date__lt=timezone.now().date()
        )
    
    # Filtrer par utilisateur
    if user_id:
        debts = debts.filter(user_id=user_id)
    
    # Filtrer par type
    if debt_type:
        debts = debts.filter(debt_type=debt_type)
    
    # Recherche
    if search:
        debts = debts.filter(
            Q(description__icontains=search) |
            Q(reason__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Stats
    total_count = debts.count()
    total_owed_to_me = debts.filter(is_paid=False, amount__gt=0).aggregate(
        s=Sum("amount")
    )["s"] or 0
    total_i_owe = debts.filter(is_paid=False, amount__lt=0).aggregate(
        s=Sum("amount")
    )["s"] or 0
    
    overdue_count = debts.filter(
        is_paid=False,
        due_date__isnull=False,
        due_date__lt=timezone.now().date()
    ).count()
    
    # Utilisateurs pour le filtre
    users = get_user_model().objects.all().order_by("username")
    
    # Pagination
    paginator = Paginator(debts, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    pagination_query = query_params.urlencode()
    
    context = {
        "page_obj": page_obj,
        "debts": page_obj.object_list,
        "users": users,
        "debt_types": Debt.DEBT_TYPE_CHOICES,
        "stats": {
            "total_count": total_count,
            "total_owed_to_me": total_owed_to_me,
            "total_i_owe": abs(total_i_owe),
            "overdue_count": overdue_count,
        },
        "filters": {
            "status": status,
            "user_id": user_id,
            "debt_type": debt_type,
            "search": search,
        },
        "pagination_query": f"&{pagination_query}" if pagination_query else "",
    }
    
    return render(request, "admin/accounting/debt_list.html", context)


@manager_required
def debt_create(request):
    """Créer une nouvelle dette"""
    if request.method == "POST":
        form = DebtForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Dette enregistrée.")
            return redirect("staff:debt_list")
    else:
        form = DebtForm()
    
    return render(request, "admin/accounting/debt_form.html", {
        "form": form,
        "mode": "create",
    })


@manager_required
def debt_detail(request, debt_id: int):
    """Détails d'une dette"""
    debt = get_object_or_404(Debt, id=debt_id)
    
    context = {
        "debt": debt,
    }
    
    return render(request, "admin/accounting/debt_detail.html", context)


@manager_required
def debt_edit(request, debt_id: int):
    """Modifier une dette"""
    debt = get_object_or_404(Debt, id=debt_id)
    
    if request.method == "POST":
        form = DebtForm(request.POST, instance=debt)
        if form.is_valid():
            form.save()
            messages.success(request, "Dette modifiée.")
            return redirect("staff:debt_list")
    else:
        form = DebtForm(instance=debt)
    
    return render(request, "admin/accounting/debt_form.html", {
        "form": form,
        "debt": debt,
        "mode": "edit",
    })


@manager_required
@require_POST
def debt_mark_paid(request, debt_id: int):
    """Marquer une dette comme payée"""
    debt = get_object_or_404(Debt, id=debt_id)
    debt.mark_as_paid()
    messages.success(request, f"Dette marquée comme payée.")
    
    return redirect(_resolve_next_url(request, "staff:debt_list"))


@manager_required
@require_POST
def debt_mark_unpaid(request, debt_id: int):
    """Annuler le paiement d'une dette"""
    debt = get_object_or_404(Debt, id=debt_id)
    debt.mark_as_unpaid()
    messages.success(request, "Statut de la dette annulé.")
    
    return redirect(_resolve_next_url(request, "staff:debt_list"))


@manager_required
@require_POST
def debt_delete(request, debt_id: int):
    """Supprimer une dette"""
    debt = get_object_or_404(Debt, id=debt_id)
    debt.delete()
    messages.success(request, "Dette supprimée.")
    return redirect(_resolve_next_url(request, "staff:debt_list"))
