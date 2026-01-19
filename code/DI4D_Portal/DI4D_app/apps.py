from django.apps import AppConfig


class Di4DAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'DI4D_app'

    def ready(self):
        # Import signal handlers
        from . import signals  # noqa: F401
