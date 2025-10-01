from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings

from .forms import CustomUserCreationForm, LoginForm, BanUserForm, UnbanUserForm
from .models import User


# ✅ Register a new user
def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # auto login after registration
            messages.success(request, "Registration successful 🎉")
            return redirect("home")
    else:
        form = CustomUserCreationForm()
    return render(request, "users/register.html", {"form": form})


# ✅ Login
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("home")
    else:
        form = LoginForm()
    return render(request, "users/login.html", {"form": form})


# ✅ Logout
@login_required
def logout_view(request):
    logout(request)
    return redirect("login")


# ✅ Show banned users (optional UI for unban)
@login_required
def banned_users_view(request):
    banned_users = User.objects.filter(is_banned=True)
    return render(request, "users/banned_users.html", {"banned_users": banned_users})
