from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from orders.models import Order, Address
from orders.utils import meals_by_price
from comptes.utils import generate_referral_code
from .forms import ProfileForm, AddressForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import UserProfile
from django.db.models import Count
from marketing.models import LoyaltyAccount
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.contrib import messages



def signup(request):
    next_url = request.GET.get('next') or request.POST.get('next') or '/'

    ref_code = request.GET.get("ref")

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            sponsor_profile = None
            if ref_code:
                sponsor_profile = UserProfile.objects.filter(
                    referral_code=ref_code
                ).first()

            profile_obj = UserProfile.objects.create(
                user=user,
                referral_code=generate_referral_code(),
                referred_by=sponsor_profile
            )

            auth_login(request, user)
            return redirect(next_url)
    else:
        form = UserCreationForm()

    return render(request, 'registration/signup.html', {
        'form': form,
        'next': next_url
    })


 
@login_required
def profile(request):
    """Vue du profil utilisateur avec commandes et fidélité"""
    
    # Récupérer ou créer le profil
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)
    if not profile_obj.referral_code:
        profile_obj.referral_code = generate_referral_code()
        profile_obj.save(update_fields=["referral_code"])

    code = profile_obj.referral_code
    # Statistiques de parrainage
    ref_delivered = (
        Order.objects
        .filter(
            user__userprofile__referred_by=profile_obj,
            status="delivered",
            counted_for_referral=True
        )
        .count()
    )

    progress = ref_delivered % 3
    remaining = 3 - progress if progress != 0 else 0

    # Gestion du formulaire de profil
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour.")
            return redirect('comptes:profile')  # Redirection pour éviter re-soumission
    else:
        form = ProfileForm(instance=profile_obj, user=request.user)

    # Récupérer le compte de fidélité
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    loyalty.recompute()

    # Filtre de statut
    status = request.GET.get("status", "all")
    
    # Récupérer les commandes avec optimisation des requêtes
    orders_qs = (
        Order.objects
        .filter(user=request.user)
        .select_related('user')
        .prefetch_related(
            'items__meal',
            'items__supplements__supplement'
        )
        .order_by("-created_at")
    )
    
    # Filtrage par statut
    if status != "all":
        orders_qs = orders_qs.filter(status=status)

    # Compteurs par statut
    status_counts = (
        Order.objects
        .filter(user=request.user)
        .values("status")
        .annotate(n=Count("id"))
    )
    counts_map = {x["status"]: x["n"] for x in status_counts}

    counts = {
        "pending": counts_map.get("pending", 0),
        "confirmed": counts_map.get("confirmed", 0),
        "delivered": counts_map.get("delivered", 0),
        "canceled": counts_map.get("canceled", 0),
    }

    points = int(loyalty.points or 0)
    points_to_discount = max(0, 10 - points)

    def pct(val: int, total: int) -> int:
        if total <= 0:
            return 0
        return int(min(100, (val / total) * 100))

    p10_pct = pct(min(points, 10), 10)


    ref_code = profile_obj.referral_code or ""

    stats = meals_by_price(request.user)

    orders_list = list(orders_qs)
    orders_view = []
    for o in orders_list:
        total_display = o.total
        if isinstance(total_display, Decimal):
            total_display = total_display.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

        orders_view.append({
            "id": o.id,
            "created_at_display": timezone.localtime(o.created_at).strftime("%d/%m/%Y %H:%M"),
            "total_display": total_display,
            "loyalty_reward": o.loyalty_reward,
            "loyalty_points_used": o.loyalty_points_used,
            "loyalty_discount": o.loyalty_discount,
            "promo_code": o.promo_code,
            "status": o.status,
            "status_display": o.get_status_display(),
        })

    orders_count = len(orders_view)



    return render(request, "registration/profile.html", {
        "form": form,
        "profile": profile_obj,
        "orders": orders_view,
        "orders_count": orders_count,
        "status": status,
        "counts": counts,
        
        # Fidélité par points
        "points": points,
        "points_to_discount": points_to_discount,
        "p10_pct": p10_pct,
        
        # Bons disponibles
        **stats,

        "ref_delivered": ref_delivered,
        "ref_progress": progress,
        "ref_remaining": remaining,
        "ref_link": request.build_absolute_uri(reverse("comptes:signup")) + (f"?ref={ref_code}" if ref_code else ""),
    })


@login_required
def add_address(request):
    """Ajouter une nouvelle adresse"""
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            try:
                address.full_clean()  # Valide avec la méthode clean() du modèle
                address.save()
                messages.success(request, "Adresse ajoutée avec succès.")
                return redirect('comptes:profile')
            except Exception as e:
                messages.error(request, f"Erreur : {str(e)}")
    else:
        form = AddressForm()
    
    return render(request, 'comptes/add_address.html', {'form': form})


@login_required
def edit_address(request, address_id):
    """Modifier une adresse existante"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            try:
                address = form.save(commit=False)
                address.full_clean()
                address.save()
                messages.success(request, "Adresse modifiée avec succès.")
                return redirect('comptes:profile')
            except Exception as e:
                messages.error(request, f"Erreur : {str(e)}")
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'comptes/edit_address.html', {
        'form': form,
        'address': address
    })


@login_required
def delete_address(request, address_id):
    """Supprimer une adresse"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        # Vérifier si c'est l'adresse par défaut
        profile = request.user.profile
        if profile.default_address == address:
            profile.default_address = None
            profile.save()
        
        address.delete()
        messages.success(request, "Adresse supprimée.")
        return redirect('comptes:profile')
    
    return render(request, 'comptes/delete_address.html', {'address': address})
