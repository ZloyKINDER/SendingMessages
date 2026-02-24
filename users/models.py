from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True, verbose_name='Email')
    avatar = models.ImageField(upload_to='users/avatars/', null=True, blank=True, verbose_name='Аватар')
    phone = models.CharField(max_length=35, null=True, blank=True, verbose_name='Телефон')
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name='Страна')
    is_blocked = models.BooleanField(default=False, verbose_name='Заблокирован')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        permissions = [
            ('can_block_user', 'Может блокировать пользователя'),
        ]

    def __str__(self):
        return self.email