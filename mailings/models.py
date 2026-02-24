from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Recipient(models.Model):
    """Модель получателя рассылки"""
    email = models.EmailField(unique=True, verbose_name='Email')
    full_name = models.CharField(max_length=255, verbose_name='Ф.И.О.')
    comment = models.TextField(blank=True, verbose_name='Комментарий')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipients',
                              verbose_name='Владелец', null=True, blank=True)

    class Meta:
        verbose_name = 'Получатель'
        verbose_name_plural = 'Получатели'

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class Message(models.Model):
    """Модель сообщения для рассылки"""
    subject = models.CharField(max_length=255, verbose_name='Тема письма')
    body = models.TextField(verbose_name='Тело письма')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages',
                              verbose_name='Владелец', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'

    def __str__(self):
        return self.subject


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

    class Meta:
        verbose_name = 'Рассылка'
        verbose_name_plural = 'Рассылки'

    def __str__(self):
        return f"Рассылка #{self.id} - {self.message.subject}"

    def get_dynamic_status(self):
        """Вычисление статуса рассылки на основе текущего времени"""
        now = timezone.now()

        if now < self.start_time:
            return 'created'
        elif self.start_time <= now <= self.end_time and self.is_active:
            return 'started'
        else:
            return 'completed'


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
        return f"Попытка #{self.id} - {self.attempt_time}"