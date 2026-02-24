from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.core.cache import cache
from .models import Mailing, Message, Recipient, MailingAttempt
from .forms import MailingForm, MessageForm, RecipientForm


def home(request):
    """Главная страница со статистикой"""
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
        attempts_stats = MailingAttempt.objects.filter(mailing__owner=request.user).values('status').annotate(
            count=Count('id'))

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


# CRUD для сообщений
class MessageListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Message
    template_name = 'mailings/message_list.html'
    context_object_name = 'messages'


class MessageDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Message
    template_name = 'mailings/message_detail.html'

    def test_func(self):
        message = self.get_object()
        return self.request.user == message.owner or self.request.user.has_perm('mailings.can_view_all_messages')


class MessageCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')


class MessageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    form_class = MessageForm
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        message = self.get_object()
        return self.request.user == message.owner


class MessageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    template_name = 'mailings/message_confirm_delete.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        message = self.get_object()
        return self.request.user == message.owner


# CRUD для получателей
class RecipientListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Recipient
    template_name = 'mailings/recipient_list.html'
    context_object_name = 'recipients'


class RecipientDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Recipient
    template_name = 'mailings/recipient_detail.html'

    def test_func(self):
        recipient = self.get_object()
        return self.request.user == recipient.owner or self.request.user.has_perm('mailings.can_view_all_recipients')


class RecipientCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')


class RecipientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Recipient
    form_class = RecipientForm
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        recipient = self.get_object()
        return self.request.user == recipient.owner


class RecipientDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Recipient
    template_name = 'mailings/recipient_confirm_delete.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        recipient = self.get_object()
        return self.request.user == recipient.owner


# CRUD для рассылок
class MailingListView(LoginRequiredMixin, OwnerQuerysetMixin, ListView):
    model = Mailing
    template_name = 'mailings/mailing_list.html'
    context_object_name = 'mailings'


class MailingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Mailing
    template_name = 'mailings/mailing_detail.html'

    def test_func(self):
        mailing = self.get_object()
        return self.request.user == mailing.owner or self.request.user.has_perm('mailings.can_view_all_mailings')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mailing = self.get_object()
        context['dynamic_status'] = mailing.get_dynamic_status()
        context['attempts'] = MailingAttempt.objects.filter(mailing=mailing)[:10]
        return context


class MailingCreateView(LoginRequiredMixin, OwnerMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Фильтруем сообщения и получателей только для текущего пользователя
        kwargs['initial'] = {
            'recipients': Recipient.objects.filter(owner=self.request.user),
            'message': Message.objects.filter(owner=self.request.user)
        }
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        return response


class MailingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def test_func(self):
        mailing = self.get_object()
        return self.request.user == mailing.owner


class MailingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Mailing
    template_name = 'mailings/mailing_confirm_delete.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def test_func(self):
        mailing = self.get_object()
        return self.request.user == mailing.owner


@login_required
def send_mailing(request, pk):
    """Ручной запуск рассылки"""
    mailing = get_object_or_404(Mailing, pk=pk)

    # Проверка прав
    if request.user != mailing.owner and not request.user.has_perm('mailings.can_view_all_mailings'):
        messages.error(request, 'У вас нет прав для запуска этой рассылки')
        return redirect('mailings:mailing_detail', pk=pk)

    # Проверка статуса
    if mailing.get_dynamic_status() != 'started':
        messages.error(request, 'Рассылка не может быть запущена в данный момент')
        return redirect('mailings:mailing_detail', pk=pk)

    # Отправка рассылки
    success_count = 0
    failed_count = 0

    for recipient in mailing.recipients.all():
        try:
            send_mail(
                subject=mailing.message.subject,
                message=mailing.message.body,
                from_email=settings.EMAIL_HOST_USER,
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
        if self.request.user.has_perm('mailings.can_view_all_mailings'):
            return queryset
        return queryset.filter(mailing__owner=self.request.user)