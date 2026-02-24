from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, verbose_name='Email')
    avatar = models.ImageField(upload_to='users/avatars/', null=True, blank=True, verbose_name='Аватар')
    phone = models.CharField(max_length=35, null=True, blank=True, verbose_name='Телефон')
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name='Страна')
    is_blocked = models.BooleanField(default=False, verbose_name='Заблокирован')
    is_verified = models.BooleanField(default=False, verbose_name='Email подтвержден')
    email_verification_token = models.CharField(max_length=100, null=True, blank=True, verbose_name='Токен подтверждения')
    email_verification_sent_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата отправки подтверждения')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        permissions = [
            ('can_block_user', 'Может блокировать пользователя'),
            ('can_view_all_users', 'Может просматривать всех пользователей'),
        ]

    def __str__(self):
        return self.email

    def generate_verification_token(self):
        """Генерация токена для подтверждения email"""
        self.email_verification_token = uuid.uuid4().hex
        self.email_verification_sent_at = timezone.now()
        self.save()
        return self.email_verification_token