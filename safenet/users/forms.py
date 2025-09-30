from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, BanHistory


# ✅ Registration form (extends Django’s UserCreationForm)
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "role")  # password1, password2 come automatically


# ✅ Login form (Django’s built-in AuthenticationForm)
class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username")
    password = forms.CharField(widget=forms.PasswordInput)


# ✅ Ban form (for moderators/admins)
class BanUserForm(forms.ModelForm):
    class Meta:
        model = BanHistory
        fields = ["reason", "start_date", "end_date"]


# ✅ Unban form (simple hidden field with user_id)
class UnbanUserForm(forms.Form):
    user_id = forms.IntegerField(widget=forms.HiddenInput())
