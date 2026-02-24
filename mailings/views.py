from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.urls import reverse_lazy
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from .models import Mailing, Message, Recipient, MailingAttempt
from .forms import MailingForm, MessageForm, RecipientForm


# Миксины для кеширования
class CacheMixin:
    """Mixin для кеширования представлений"""

    @method_decorator(cache_page(300))  # 5 минут
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class CacheForAnonymousMixin:
    """Mixin для кеширования только для анонимных пользователей"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return cache_page(300)(super().dispatch)(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)


def home(request):
    """Главная страница со статистикой (с кешированием)"""
    # Пытаемся получить данные из кеша
    cache_key = f'home_stats_{request.user.id if request.user.is_authenticated else "anonymous"}'
    context = cache.get(cache_key)

    if not context:
        if request.user.is_authenticated:
            # Для авторизованных пользователей показываем их статистику
            mailings = Mailing.objects.filter(owner=request.user)
            recipients = Recipient.objects.filter(owner=request.user)

            total_mailings = mailings.count()
            active_mailings = mailings.filter(
                start_time__lte=timezone.now(),
                end_time__gte=timezone.now(),
                is_active=True
            ).count()
            total_recipients = recipients.count()

            # Статистика по попыткам
            attempts_stats = MailingAttempt.objects.filter(
                mailing__owner=request.user
            ).values('status').annotate(count=Count('id'))

            context = {
                'total_mailings': total_mailings,
                'active_mailings': active_mailings,
                'total_recipients': total_recipients,
                'attempts_stats': attempts_stats,
            }
        else:
            # Для неавторизованных показываем общую статистику
            total_mailings = Mailing.objects.count()
            active_mailings = Mailing.objects.filter(
                start_time__lte=timezone.now(),
                end_time__gte=timezone.now(),
                is_active=True
            ).count()
            total_recipients = Recipient.objects.count()

            context = {
                'total_mailings': total_mailings,
                'active_mailings': active_mailings,
                'total_recipients': total_recipients,
            }

        # Сохраняем в кеш на 5 минут
        cache.set(cache_key, context, 300)

    return render(request, 'mailings/home.html', context)


class OwnerMixin:
    """Mixin для автоматической установки владельца"""

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerQuerysetMixin:
    """Mixin для фильтрации queryset по владельцу"""

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            return queryset
        return queryset.filter(owner=self.request.user)


class ManagerRequiredMixin(PermissionRequiredMixin):
    """Mixin для проверки прав менеджера"""
    permission_required = 'mailings.can_view_all_mailings'


class OwnerOrManagerMixin(UserPassesTestMixin):
    """Mixin для проверки: владелец или менеджер"""

    def test_func(self):
        obj = self.get_object()
        user = self.request.user

        # Менеджеры могут просматривать всё
        if user.has_perm('mailings.can_view_all_mailings'):
            return True

        # Обычные пользователи могут работать только со своим
        return obj.owner == user


# CRUD для сообщений
class MessageListView(LoginRequiredMixin, OwnerQuerysetMixin, CacheMixin, ListView):
    model = Message
    template_name = 'mailings/message_list.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.has_perm('mailings.can_view_all_messages'):
            return Message.objects.all()
        return Message.objects.filter(owner=self.request.user)

    def get_cache_key(self):
        """Генерирует уникальный ключ кеша для текущего пользователя"""
        return f'message_list_user_{self.request.user.id}'


class MessageDetailView(LoginRequiredMixin, OwnerOrManagerMixin, DetailView):
    model = Message
    template_name = 'mailings/message_detail.html'


class MessageCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)

        # Очищаем кеш для списка сообщений
        cache.delete_pattern('*message_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_messages*')

        # Добавляем сообщение об успехе
        from django.contrib import messages
        messages.success(self.request, 'Сообщение успешно создано!')

        return response


class MessageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        message = self.get_object()
        return self.request.user == message.owner

    def form_valid(self, form):
        response = super().form_valid(form)
        # Очищаем кеш после обновления
        cache.delete_pattern('*message_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_messages*')
        messages.success(self.request, 'Сообщение успешно обновлено!')
        return response


class MessageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    template_name = 'mailings/message_confirm_delete.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        message = self.get_object()
        return self.request.user == message.owner

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        cache.delete_pattern('*message_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_messages*')
        messages.success(request, 'Сообщение успешно удалено!')
        return response


# CRUD для получателей
class RecipientListView(LoginRequiredMixin, OwnerQuerysetMixin, CacheMixin, ListView):
    model = Recipient
    template_name = 'mailings/recipient_list.html'
    context_object_name = 'recipients'
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.has_perm('mailings.can_view_all_recipients'):
            return Recipient.objects.all()
        return Recipient.objects.filter(owner=self.request.user)

    def get_cache_key(self):
        """Генерирует уникальный ключ кеша для текущего пользователя"""
        return f'recipient_list_user_{self.request.user.id}'


class RecipientDetailView(LoginRequiredMixin, OwnerOrManagerMixin, DetailView):
    model = Recipient
    template_name = 'mailings/recipient_detail.html'


class RecipientCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)

        cache.delete_pattern('*recipient_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_recipients*')

        messages.success(self.request, 'Получатель успешно создан!')

        return response


class RecipientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        recipient = self.get_object()
        return self.request.user == recipient.owner

    def form_valid(self, form):
        response = super().form_valid(form)
        cache.delete_pattern('*recipient_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_recipients*')
        messages.success(self.request, 'Получатель успешно обновлен!')
        return response


class RecipientDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Recipient
    template_name = 'mailings/recipient_confirm_delete.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        recipient = self.get_object()
        return self.request.user == recipient.owner

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)
        cache.delete_pattern('*recipient_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_recipients*')
        messages.success(request, 'Получатель успешно удален!')
        return response


# CRUD для рассылок
class MailingListView(LoginRequiredMixin, OwnerQuerysetMixin, CacheMixin, ListView):
    model = Mailing
    template_name = 'mailings/mailing_list.html'
    context_object_name = 'mailings'
    paginate_by = 20

    def get_queryset(self):
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            return Mailing.objects.all()
        return Mailing.objects.filter(owner=self.request.user)

    def get_cache_key(self):
        """Генерирует уникальный ключ кеша для текущего пользователя"""
        return f'mailing_list_user_{self.request.user.id}'

    def get_cache_timeout(self):
        """Разное время кеширования для разных пользователей"""
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            return 60  # 1 минута для менеджеров
        return 300  # 5 минут для обычных пользователей


class MailingDetailView(LoginRequiredMixin, OwnerOrManagerMixin, DetailView):
    model = Mailing
    template_name = 'mailings/mailing_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mailing = self.get_object()
        context['dynamic_status'] = mailing.get_dynamic_status()

        # Кешируем попытки
        cache_key = f'mailing_attempts_{mailing.id}'
        attempts = cache.get(cache_key)
        if not attempts:
            attempts = MailingAttempt.objects.filter(mailing=mailing)[:10]
            cache.set(cache_key, attempts, 60)  # Кешируем на 1 минуту

        context['attempts'] = attempts
        return context


class MailingCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'recipients': Recipient.objects.filter(owner=self.request.user),
            'message': Message.objects.filter(owner=self.request.user)
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_messages'] = Message.objects.filter(owner=self.request.user)
        context['available_recipients'] = Recipient.objects.filter(owner=self.request.user)
        return context

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        cache.delete_pattern('*mailing_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_mailings*')
        messages.success(self.request, 'Рассылка успешно создана!')

        return response


class MailingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def test_func(self):
        mailing = self.get_object()
        return self.request.user == mailing.owner

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['available_messages'] = Message.objects.filter(owner=self.request.user)
        context['available_recipients'] = Recipient.objects.filter(owner=self.request.user)
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        cache.delete_pattern('*mailing_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_mailings*')
        cache.delete(f'mailing_status_{self.object.id}')
        return response


class MailingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Mailing
    template_name = 'mailings/mailing_confirm_delete.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def test_func(self):
        mailing = self.get_object()
        return self.request.user == mailing.owner

    def delete(self, request, *args, **kwargs):
        mailing_id = self.get_object().id

        response = super().delete(request, *args, **kwargs)
        cache.delete_pattern('*mailing_list*')
        cache.delete_pattern(f'*user_{self.request.user.id}_mailings*')
        cache.delete(f'mailing_status_{mailing_id}')

        messages.success(request, 'Рассылка успешно удалена!')

        return response


@login_required
def send_mailing(request, pk):
    """Ручной запуск рассылки"""
    mailing = get_object_or_404(Mailing, pk=pk)

    # Проверка прав
    if request.user != mailing.owner and not request.user.has_perm('mailings.can_view_all_mailings'):
        messages.error(request, 'У вас нет прав для запуска этой рассылки')
        return redirect('mailings:mailing_detail', pk=pk)

    # Проверка статуса
    dynamic_status = mailing.get_dynamic_status()
    if dynamic_status != 'started':
        messages.error(request,
                       f'Рассылка не может быть запущена в данный момент. Текущий статус: {mailing.get_status_display()}')
        return redirect('mailings:mailing_detail', pk=pk)

    # Отправка рассылки
    success_count = 0
    failed_count = 0

    for recipient in mailing.recipients.all():
        try:
            send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient.email],
                fail_silently=False,
            )
            status = 'success'
            response = 'Письмо успешно отправлено'
            success_count += 1
        except Exception as e:
            status = 'failed'
            response = str(e)
            failed_count += 1

        MailingAttempt.objects.create(
            status=status,
            server_response=response,
            mailing=mailing,
            recipient=recipient
        )

    messages.success(request, f'Рассылка завершена. Успешно: {success_count}, Ошибок: {failed_count}')

    # Очищаем кеш попыток
    cache.delete(f'mailing_attempts_{mailing.id}')

    return redirect('mailings:mailing_detail', pk=pk)


@login_required
def toggle_mailing_active(request, pk):
    """Включение/отключение рассылки"""
    mailing = get_object_or_404(Mailing, pk=pk)

    if request.user == mailing.owner or request.user.has_perm('mailings.can_disable_mailing'):
        mailing.is_active = not mailing.is_active
        mailing.save()
        status = 'активирована' if mailing.is_active else 'отключена'
        messages.success(request, f'Рассылка {status}')

        # Очищаем кеш
        cache.delete(f'mailing_status_{mailing.id}')
        cache.delete_pattern('mailing_list_*')
    else:
        messages.error(request, 'У вас нет прав для изменения статуса рассылки')

    return redirect('mailings:mailing_detail', pk=pk)


class MailingAttemptListView(LoginRequiredMixin, ListView):
    model = MailingAttempt
    template_name = 'mailings/attempt_list.html'
    context_object_name = 'attempts'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()

        # Менеджеры видят все попытки
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            return queryset

        # Обычные пользователи видят только попытки своих рассылок
        return queryset.filter(mailing__owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Добавляем статистику по попыткам
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            queryset = MailingAttempt.objects.all()
        else:
            queryset = MailingAttempt.objects.filter(mailing__owner=self.request.user)

        context['total_attempts'] = queryset.count()
        context['successful_attempts'] = queryset.filter(status='success').count()
        context['failed_attempts'] = queryset.filter(status='failed').count()

        return context


# Кастомная команда для отправки рассылок (будет вызываться из cron)
def send_scheduled_mailings():
    """Функция для отправки запланированных рассылок"""
    now = timezone.now()
    mailings = Mailing.objects.filter(
        start_time__lte=now,
        end_time__gte=now,
        is_active=True
    )

    for mailing in mailings:
        for recipient in mailing.recipients.all():
            try:
                send_mail(
                    subject=mailing.message.subject,
                    message=mailing.message.body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient.email],
                    fail_silently=False,
                )
                MailingAttempt.objects.create(
                    status='success',
                    server_response='Письмо успешно отправлено',
                    mailing=mailing,
                    recipient=recipient
                )
            except Exception as e:
                MailingAttempt.objects.create(
                    status='failed',
                    server_response=str(e),
                    mailing=mailing,
                    recipient=recipient
                )