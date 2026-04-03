from django.apps import AppConfig


class GestionVentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gestion_ventas"

    def ready(self):
        import gestion_ventas.signals  # noqa: F401
