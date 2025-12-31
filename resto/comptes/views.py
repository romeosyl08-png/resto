from django.shortcuts import render, redirect
from orders.models import Order
from .forms import ProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login
from .models import  UserProfile
from django.shortcuts import render
from django.db.models import Count
from marketing.models import LoyaltyAccount, FreeItemVoucher

def signup(request):
    next_url = request.GET.get('next') or request.POST.get('next') or '/'
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            from .models import UserProfile
            UserProfile.objects.create(user=user)
            auth_login(request, user)
            return redirect(next_url)
    else:
        form = UserCreationForm()
    return render(request, 'registration/signup.html', {'form': form, 'next': next_url})



@login_required
def profile(request):
    profile_obj, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
    else:
        form = ProfileForm(instance=profile_obj)

    # --- Fidélité ---
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    
    vouchers_available = FreeItemVoucher.objects.filter(user=request.user,status="AVAILABLE").count()

    # --- Filtre statut commandes ---
    status = request.GET.get("status", "all")
    qs = Order.objects.filter(user=request.user).order_by("-created_at")
    if status != "all":
        qs = qs.filter(status=status)

    # Stats par statut (pour afficher des compteurs)
    status_counts = (
        Order.objects.filter(user=request.user)
        .values("status")
        .annotate(n=Count("id"))
    )
    counts_map = {x["status"]: x["n"] for x in status_counts}

    return render(request, "registration/profile.html", {
        "form": form,
        "orders": qs,
        "status": status,
        "counts": counts_map,

        "loyalty_points": loyalty.points,         # points restants (0..7)
        "free_vouchers": vouchers_available,      # bons gratuits dispo
    })
