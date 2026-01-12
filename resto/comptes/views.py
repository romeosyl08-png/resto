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

    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)

    free_vouchers = FreeItemVoucher.objects.filter(
        user=request.user,
        status=FreeItemVoucher.Status.AVAILABLE
    ).count()

    status = request.GET.get("status", "all")
    qs = Order.objects.filter(user=request.user).order_by("-created_at")
    if status != "all":
        qs = qs.filter(status=status)

    status_counts = (
        Order.objects.filter(user=request.user)
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

    return render(request, "registration/profile.html", {
        "form": form,
        "profile": profile_obj,   # <-- AJOUT
        "orders": qs,
        "status": status,
        "counts": counts,
        "loyalty_points": loyalty.stamps,
        "free_vouchers": free_vouchers,
    })
