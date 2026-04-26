from django.apps import AppConfig


class HousekeepingConfig(AppConfig):
    name = 'housekeeping'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals
