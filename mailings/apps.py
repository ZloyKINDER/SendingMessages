from django.apps import AppConfig


class MailingsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mailings'
    verbose_name = 'Управление рассылками'

    def ready(self):
        import mailings.signals  # noqa
