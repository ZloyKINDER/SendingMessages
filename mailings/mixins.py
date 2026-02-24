from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.conf import settings


class CacheMixin:
    """Mixin для кеширования представлений"""

    @method_decorator(cache_page(settings.CACHE_MIDDLEWARE_SECONDS))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class CacheForAnonymousMixin:
    """Mixin для кеширования только для анонимных пользователей"""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return cache_page(settings.CACHE_MIDDLEWARE_SECONDS)(super().dispatch)(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)