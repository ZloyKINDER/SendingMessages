from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from mailings.models import Mailing, MailingAttempt
from datetime import datetime, timedelta
import logging

# Настройка логирования
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправка запланированных рассылок'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mailing-id',
            type=int,
            help='ID конкретной рассылки для отправки'
        )
        parser.add_argument(
            '--user-email',
            type=str,
            help='Email пользователя, чьи рассылки отправить'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительная отправка даже если рассылка не в статусе "Запущена"'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Пробный запуск без реальной отправки'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ЗАПУСК ОТПРАВКИ РАССЫЛОК'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Получаем параметры
        mailing_id = options.get('mailing_id')
        user_email = options.get('user_email')
        force = options.get('force', False)
        dry_run = options.get('dry_run', False)

        # Формируем queryset рассылок
        mailings = self.get_mailings_queryset(mailing_id, user_email, force)

        if not mailings.exists():
            self.stdout.write(self.style.WARNING('Нет рассылок для отправки'))
            return

        self.stdout.write(self.style.SUCCESS(f'Найдено рассылок для отправки: {mailings.count()}'))

        # Отправляем рассылки
        results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0
        }

        for mailing in mailings:
            result = self.process_mailing(mailing, force, dry_run)
            results['total'] += 1
            results['success'] += 1 if result['success'] else 0
            results['failed'] += 1 if result['failed'] else 0
            results['skipped'] += 1 if result['skipped'] else 0

        # Выводим итоги
        self.print_summary(results, dry_run)

    def get_mailings_queryset(self, mailing_id=None, user_email=None, force=False):
        """Получение queryset рассылок для отправки"""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Базовый queryset
        if mailing_id:
            # Конкретная рассылка по ID
            mailings = Mailing.objects.filter(id=mailing_id)
            self.stdout.write(self.style.SUCCESS(f'Режим: отправка конкретной рассылки ID={mailing_id}'))
        else:
            # Все активные рассылки
            now = timezone.now()
            if force:
                # Принудительно все активные
                mailings = Mailing.objects.filter(is_active=True)
                self.stdout.write(self.style.WARNING('Режим: принудительная отправка всех активных рассылок'))
            else:
                # Только те, которые должны быть запущены сейчас
                mailings = Mailing.objects.filter(
                    start_time__lte=now,
                    end_time__gte=now,
                    is_active=True
                )
                self.stdout.write(self.style.SUCCESS('Режим: отправка рассылок по расписанию'))

        # Фильтр по пользователю
        if user_email:
            try:
                user = User.objects.get(email=user_email)
                mailings = mailings.filter(owner=user)
                self.stdout.write(self.style.SUCCESS(f'Фильтр: только рассылки пользователя {user_email}'))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Пользователь с email {user_email} не найден'))
                return Mailing.objects.none()

        return mailings

    def process_mailing(self, mailing, force=False, dry_run=False):
        """Обработка одной рассылки"""
        self.stdout.write(self.style.SUCCESS('-' * 40))
        self.stdout.write(f'Рассылка #{mailing.id}: {mailing.message.subject}')
        self.stdout.write(f'  Владелец: {mailing.owner.email if mailing.owner else "Нет"}')
        self.stdout.write(
            f'  Период: {mailing.start_time.strftime("%d.%m.%Y %H:%M")} - {mailing.end_time.strftime("%d.%m.%Y %H:%M")}')

        # Проверка статуса
        dynamic_status = mailing.get_dynamic_status()
        self.stdout.write(f'  Статус: {dynamic_status}')

        if not force and dynamic_status != 'started':
            self.stdout.write(
                self.style.WARNING(f'  Пропущена: рассылка не в статусе "Запущена" (текущий: {dynamic_status})'))
            return {'success': False, 'failed': False, 'skipped': True}

        recipients = mailing.recipients.all()
        self.stdout.write(f'  Получателей: {recipients.count()}')

        if not recipients.exists():
            self.stdout.write(self.style.WARNING('  Пропущена: нет получателей'))
            return {'success': False, 'failed': False, 'skipped': True}

        if dry_run:
            self.stdout.write(self.style.WARNING('  ПРОБНЫЙ ЗАПУСК: отправка не производится'))
            return {'success': True, 'failed': False, 'skipped': False}

        # Отправка рассылки
        success_count = 0
        failed_count = 0

        for recipient in recipients:
            try:
                if self.send_email(mailing, recipient):
                    success_count += 1
                    self.create_attempt(mailing, recipient, 'success', 'Письмо успешно отправлено')
                else:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                self.create_attempt(mailing, recipient, 'failed', str(e))
                self.stdout.write(self.style.ERROR(f'    Ошибка для {recipient.email}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'  Результат: успешно {success_count}, ошибок {failed_count}'))

        return {
            'success': success_count > 0,
            'failed': failed_count > 0,
            'skipped': False,
            'success_count': success_count,
            'failed_count': failed_count
        }

    def send_email(self, mailing, recipient):
        """Отправка одного письма"""
        send_mail(
            subject=mailing.message.subject,
            message=mailing.message.body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
        return True

    def create_attempt(self, mailing, recipient, status, response):
        """Создание записи о попытке отправки"""
        MailingAttempt.objects.create(
            status=status,
            server_response=response,
            mailing=mailing,
            recipient=recipient
        )

    def print_summary(self, results, dry_run=False):
        """Вывод итоговой статистики"""
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('ИТОГИ ОТПРАВКИ'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Всего обработано рассылок: {results["total"]}')
        self.stdout.write(f'Успешно отправлено: {results["success"]}')
        self.stdout.write(f'С ошибками: {results["failed"]}')
        self.stdout.write(f'Пропущено: {results["skipped"]}')

        if dry_run:
            self.stdout.write(self.style.WARNING('Это был ПРОБНЫЙ ЗАПУСК. Реальная отправка не производилась.'))