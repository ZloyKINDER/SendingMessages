from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import UserRegistrationForm, UserProfileForm
from .models import User


def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно!')
            return redirect('mailings:home')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_blocked:
                messages.error(request, 'Ваш аккаунт заблокирован')
            else:
                login(request, user)
                return redirect('mailings:home')
        else:
            messages.error(request, 'Неверный email или пароль')

    return render(request, 'users/login.html')


def user_logout(request):
    logout(request)
    return redirect('mailings:home')


@login_required
def profile(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен')
            return redirect('users:profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'users/profile.html', {'form': form})


class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    permission_required = 'users.can_block_user'


@login_required
def block_user(request, user_id):
    if not request.user.has_perm('users.can_block_user'):
        messages.error(request, 'У вас нет прав для блокировки пользователей')
        return redirect('users:user_list')

    user = get_object_or_404(User, id=user_id)
    if user != request.user:  # Нельзя заблокировать самого себя
        user.is_blocked = not user.is_blocked
        user.save()
        status = 'заблокирован' if user.is_blocked else 'разблокирован'
        messages.success(request, f'Пользователь {user.email} {status}')
    else:
        messages.error(request, 'Вы не можете заблокировать самого себя')

    return redirect('users:user_list')