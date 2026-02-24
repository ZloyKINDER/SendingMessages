from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .models import Mailing


@receiver(pre_save, sender=Mailing)
def validate_mailing_dates(sender, instance, **kwargs):
    """Валидация дат перед сохранением"""
    if instance.start_time and instance.end_time:
        if instance.start_time >= instance.end_time:
            raise ValidationError('Дата начала должна быть раньше даты окончания')