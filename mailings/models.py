from django.db import models
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

User = get_user_model()


class Recipient(models.Model):
    """Модель получателя рассылки"""
    email = models.EmailField(unique=True, verbose_name='Email')
    full_name = models.CharField(max_length=255, verbose_name='Ф.И.О.')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipients',
                              verbose_name='Владелец', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Получатель'
        verbose_name_plural = 'Получатели'
        ordering = ['-created_at']
        permissions = [
            ('can_view_all_recipients', 'Может просматривать всех получателей'),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def save(self, *args, **kwargs):
        # Очищаем кеш при сохранении
        cache.delete_pattern('recipient_list_*')
        super().save(*args, **kwargs)


class Message(models.Model):
    """Модель сообщения для рассылки"""
    subject = models.CharField(max_length=255, verbose_name='Тема письма')
    body = models.TextField(verbose_name='Тело письма')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages',
                              verbose_name='Владелец', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['-created_at']
        permissions = [
            ('can_view_all_messages', 'Может просматривать все сообщения'),
        ]

    def __str__(self):
        return self.subject

    def save(self, *args, **kwargs):
        # Очищаем кеш при сохранении
        cache.delete_pattern('message_list_*')
        super().save(*args, **kwargs)


class Mailing(models.Model):
    """Модель рассылки"""

    STATUS_CHOICES = [
        ('created', 'Создана'),
        ('started', 'Запущена'),
        ('completed', 'Завершена'),
    ]

    start_time = models.DateTimeField(verbose_name='Дата и время начала')
    end_time = models.DateTimeField(verbose_name='Дата и время окончания')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created',
                              verbose_name='Статус')
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='mailings',
                                verbose_name='Сообщение')
    recipients = models.ManyToManyField(Recipient, related_name='mailings',
                                        verbose_name='Получатели')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mailings',
                              verbose_name='Владелец', null=True, blank=True)
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'
        ordering = ['-created_at']
        permissions = [
            ('can_view_all_mailings', 'Может просматривать все рассылки'),
            ('can_disable_mailing', 'Может отключать рассылки'),
        ]

    def __str__(self):
        return f"Рассылка #{self.id} - {self.message.subject}"

    def clean(self):
        """Валидация модели"""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError('Дата начала должна быть раньше даты окончания')

            if self.start_time < timezone.now():
                raise ValidationError('Дата начала не может быть в прошлом')

    def save(self, *args, **kwargs):
        # Валидация
        self.full_clean()

        # Очищаем кеш при сохранении
        cache.delete(f'mailing_status_{self.id}')
        cache.delete_pattern('mailing_list_*')

        super().save(*args, **kwargs)

    def get_dynamic_status(self):
        """Вычисление статуса рассылки на основе текущего времени с кешированием"""
        cache_key = f'mailing_status_{self.id}'
        status = cache.get(cache_key)

        if not status:
            now = timezone.now()

            if now < self.start_time:
                status = 'created'
            elif self.start_time <= now <= self.end_time and self.is_active:
                status = 'started'
            else:
                status = 'completed'

            # Кешируем на 60 секунд
            cache.set(cache_key, status, 60)

        return status

    def get_status_display(self):
        """Возвращает отображаемое название статуса"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.status, self.status)


class MailingAttempt(models.Model):
    """Модель попытки рассылки"""

    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('failed', 'Не успешно'),
    ]

    attempt_time = models.DateTimeField(auto_now_add=True, verbose_name='Дата и время попытки')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name='Статус')
    server_response = models.TextField(blank=True, verbose_name='Ответ сервера')
    mailing = models.ForeignKey(Mailing, on_delete=models.CASCADE, related_name='attempts',
                                verbose_name='Рассылка')
    recipient = models.ForeignKey(Recipient, on_delete=models.CASCADE, related_name='attempts',
                                  verbose_name='Получатель', null=True, blank=True)

    class Meta:
        verbose_name = 'Попытка рассылки'
        verbose_name_plural = 'Попытки рассылок'
        ordering = ['-attempt_time']

    def __str__(self):
        return f"Попытка #{self.id} - {self.attempt_time.strftime('%d.%m.%Y %H:%M')}"

    def save(self, *args, **kwargs):
        # Очищаем кеш попыток при сохранении
        cache.delete(f'mailing_attempts_{self.mailing_id}')
        super().save(*args, **kwargs)


@receiver(post_save, sender=Mailing)
@receiver(post_delete, sender=Mailing)
def clear_mailing_cache(sender, instance, **kwargs):
    """Очистка кеша при изменениях в рассылках"""
    cache.delete_pattern('*mailing_list*')
    cache.delete(f'mailing_status_{instance.id}')
    if instance.owner:
        cache.delete_pattern(f'*user_{instance.owner.id}_mailings*')


@receiver(post_save, sender=Message)
@receiver(post_delete, sender=Message)
def clear_message_cache(sender, **kwargs):
    """Очистка кеша при изменениях в сообщениях"""
    cache.delete_pattern('message_list_*')


@receiver(post_save, sender=Recipient)
@receiver(post_delete, sender=Recipient)
def clear_recipient_cache(sender, instance, **kwargs):
    """Очистка кеша при изменениях в получателях"""
    cache.delete_pattern('*recipient_list*')
    if instance.owner:
        cache.delete_pattern(f'*user_{instance.owner.id}_recipients*')


@receiver(post_save, sender=MailingAttempt)
@receiver(post_delete, sender=MailingAttempt)
def clear_attempt_cache(sender, instance, **kwargs):
    """Очистка кеша при изменениях в попытках"""
    cache.delete(f'mailing_attempts_{instance.mailing_id}')