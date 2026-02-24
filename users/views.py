from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin, LoginRequiredMixin
from django.views.generic import ListView
from django.utils import timezone
from datetime import timedelta
from .forms import UserRegistrationForm, UserProfileForm
from .models import User
from .services import send_verification_email


def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.is_verified = False
            user.save()

            # Отправка письма для подтверждения
            send_verification_email(user, request)

            messages.success(request, 'Регистрация прошла успешно! На ваш email отправлено письмо с подтверждением.')
            return redirect('users:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'users/register.html', {'form': form})


def verify_email(request, token):
    """Подтверждение email по токену"""
    try:
        user = User.objects.get(email_verification_token=token)

        # Проверка, не истек ли токен (24 часа)
        if user.email_verification_sent_at and \
                user.email_verification_sent_at + timedelta(hours=24) > timezone.now():
            user.is_verified = True
            user.email_verification_token = None
            user.email_verification_sent_at = None
            user.save()
            messages.success(request, 'Email успешно подтвержден! Теперь вы можете войти в систему.')
        else:
            messages.error(request, 'Ссылка для подтверждения устарела. Запросите новую.')
    except User.DoesNotExist:
        messages.error(request, 'Недействительная ссылка для подтверждения.')

    return redirect('users:login')


def resend_verification(request):
    """Повторная отправка письма для подтверждения"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email, is_verified=False)
            send_verification_email(user, request)
            messages.success(request, 'Письмо с подтверждением отправлено повторно.')
        except User.DoesNotExist:
            messages.error(request, 'Пользователь с таким email не найден или уже подтвержден.')

    return render(request, 'users/resend_verification.html')


def user_login(request):
    """Вход пользователя"""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)

        if user is not None:
            if user.is_blocked:
                messages.error(request, 'Ваш аккаунт заблокирован. Обратитесь к администратору.')
            elif not user.is_verified:
                messages.warning(request, 'Пожалуйста, подтвердите ваш email перед входом.')
                return render(request, 'users/login.html', {'email': email, 'need_verification': True})
            else:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.email}!')
                return redirect('mailings:home')
        else:
            messages.error(request, 'Неверный email или пароль.')

    return render(request, 'users/login.html')


def user_logout(request):
    """Выход пользователя"""
    logout(request)
    messages.info(request, 'Вы вышли из системы.')
    return redirect('mailings:home')


@login_required
def profile(request):
    """Профиль пользователя"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен.')
            return redirect('users:profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'users/profile.html', {'form': form})


class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Список пользователей (только для менеджеров)"""
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    permission_required = 'users.can_view_all_users'
    paginate_by = 20


@login_required
def block_user(request, user_id):
    """Блокировка/разблокировка пользователя (только для менеджеров)"""
    if not request.user.has_perm('users.can_block_user'):
        messages.error(request, 'У вас нет прав для блокировки пользователей.')
        return redirect('users:user_list')

    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, 'Вы не можете заблокировать самого себя.')
    else:
        user.is_blocked = not user.is_blocked
        user.save()
        status = 'заблокирован' if user.is_blocked else 'разблокирован'
        messages.success(request, f'Пользователь {user.email} {status}.')

    return redirect('users:user_list')