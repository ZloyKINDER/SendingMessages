from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_verification_email(user, request):
    """Отправка письма для подтверждения email"""
    token = user.generate_verification_token()
    verification_url = request.build_absolute_uri(
        reverse('users:verify_email', args=[token])
    )

    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': 'Сервис рассылок',
    }

    html_message = render_to_string('users/email/verification_email.html', context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject='Подтверждение email на сервисе рассылок',
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_password_reset_email(user, request):
    """Отправка письма для восстановления пароля"""
    # Используем встроенную функцию Django
    pass