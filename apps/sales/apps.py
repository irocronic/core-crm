# apps/sales/apps.py

from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sales'
    verbose_name = 'Satış Yönetimi'

    def ready(self):
        """
        Uygulama hazır olduğunda sinyallerin import edilmesini sağlar.
        Bu, sinyal alıcılarının (receiver) Django tarafından tanınması için gereklidir.
        """
        import apps.sales.signals
