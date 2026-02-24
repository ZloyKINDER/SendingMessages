from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from users.models import User
from mailings.models import Mailing, Message, Recipient


class Command(BaseCommand):
    help = 'Создание групп пользователей и назначение прав'

    def handle(self, *args, **options):
        # Создание группы менеджеров
        managers_group, created = Group.objects.get_or_create(name='Менеджеры')

        if created:
            self.stdout.write(self.style.SUCCESS('Группа "Менеджеры" создана'))
        else:
            self.stdout.write(self.style.WARNING('Группа "Менеджеры" уже существует'))

        # Очищаем старые права
        managers_group.permissions.clear()

        # Права для работы с пользователями
        user_content_type = ContentType.objects.get_for_model(User)
        user_permissions = Permission.objects.filter(
            content_type=user_content_type,
            codename__in=['can_block_user', 'can_view_all_users']
        )
        managers_group.permissions.add(*user_permissions)

        # Права для работы с рассылками
        mailing_content_type = ContentType.objects.get_for_model(Mailing)
        mailing_permissions = Permission.objects.filter(
            content_type=mailing_content_type,
            codename__in=['can_view_all_mailings', 'can_disable_mailing']
        )
        managers_group.permissions.add(*mailing_permissions)

        # Права для работы с сообщениями
        message_content_type = ContentType.objects.get_for_model(Message)
        message_permissions = Permission.objects.filter(
            content_type=message_content_type,
            codename='can_view_all_messages'
        )
        managers_group.permissions.add(*message_permissions)

        # Права для работы с получателями
        recipient_content_type = ContentType.objects.get_for_model(Recipient)
        recipient_permissions = Permission.objects.filter(
            content_type=recipient_content_type,
            codename='can_view_all_recipients'
        )
        managers_group.permissions.add(*recipient_permissions)

        self.stdout.write(
            self.style.SUCCESS(f'Назначено {managers_group.permissions.count()} прав для группы "Менеджеры"')
        )

        # Создание группы обычных пользователей (опционально)
        users_group, created = Group.objects.get_or_create(name='Пользователи')

        self.stdout.write(self.style.SUCCESS('Инициализация групп завершена'))