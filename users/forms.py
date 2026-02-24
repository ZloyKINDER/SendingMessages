from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Подтверждение пароля', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'password1', 'password2', 'first_name', 'last_name', 'phone', 'country')


class UserProfileForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone', 'country', 'avatar')
        widgets = {
            'email': forms.EmailInput(attrs={'readonly': 'readonly'}),
        }