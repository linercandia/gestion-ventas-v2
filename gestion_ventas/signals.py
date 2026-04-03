from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Cliente


User = get_user_model()


@receiver(post_save, sender=User)
def asegurar_perfil_cliente(sender, instance, created, **kwargs):
    if created:
        Cliente.objects.get_or_create(usuario=instance)
