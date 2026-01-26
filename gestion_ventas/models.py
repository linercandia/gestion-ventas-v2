import uuid
from django.db import models
from django.db.models import Sum
from django.utils import timezone 

class Producto(models.Model):
    UNIDADES = [
        ('Lb', 'Libra'),
        ('Und', 'Unidad'),
    ]
    FORMATOS = [
        ('moneda', 'Pesos Colombianos ($)'),
        ('unidades', 'Unidades (Puntos de mil)'),
    ]
    
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=5, choices=UNIDADES, default='Und')
    formato_visual = models.CharField(
        max_length=10, 
        choices=FORMATOS, 
        default='unidades',
        verbose_name="Formato de ingreso"
    )

    def __str__(self):
        return f"{self.nombre}"

class Zona(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje_comision}%)"

class Jornada(models.Model):
    fecha = models.DateField(default=timezone.now, unique=True, verbose_name="Fecha de la Jornada")
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Jornada"
        verbose_name_plural = "Jornadas"

    def __str__(self):
        return f"Jornada {self.fecha}"

class ControlZonaJornada(models.Model):
    # Genera un ID único para la sesión del navegador, evitando cruces entre vendedores
    id_sesion = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE)
    cerrada = models.BooleanField(default=False, verbose_name="¿Cerró Jornada?")
    nombre_vendedor = models.CharField(max_length=100, blank=True, null=True)
    # Aumentamos dígitos para evitar errores con cifras grandes de dinero
    dinero_entregado = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        # impide que una zona se asigne dos veces en la misma fecha
        unique_together = ('jornada', 'zona')
        verbose_name = "Control de Zona"
        verbose_name_plural = "Controles de Zonas"

    def __str__(self):
        estado = "Cerrada" if self.cerrada else "Abierta"
        return f"{self.zona.nombre} - {self.jornada.fecha} ({estado})"

class InventarioControl(models.Model):
    control = models.ForeignKey(ControlZonaJornada, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_salida = models.IntegerField(default=0)
    cantidad_llegada = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.producto.nombre} en {self.control.zona.nombre}"

class EnvioInterzona(models.Model):
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE, related_name='envios', null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    zona_origen = models.ForeignKey(Zona, related_name='envios_salientes', on_delete=models.CASCADE)
    zona_destino = models.ForeignKey(Zona, related_name='envios_entrantes', on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    aceptado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.producto} de {self.zona_origen} a {self.zona_destino}"

class RegistroVenta(models.Model):
    fecha = models.DateField(auto_now_add=True)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_salida = models.IntegerField(verbose_name="Carga Inicial")
    cantidad_llegada = models.IntegerField(verbose_name="Regresó a Bodega", default=0)

    def unidades_vendidas(self):
        recibido = EnvioInterzona.objects.filter(
            zona_destino=self.zona, 
            producto=self.producto, 
            jornada__fecha=self.fecha, # Filtrado por jornada
            aceptado=True
        ).aggregate(Sum('cantidad'))['cantidad__sum'] or 0

        entregado = EnvioInterzona.objects.filter(
            zona_origen=self.zona, 
            producto=self.producto, 
            jornada__fecha=self.fecha,
            aceptado=True
        ).aggregate(Sum('cantidad'))['cantidad__sum'] or 0

        return (self.cantidad_salida + recibido) - (entregado + self.cantidad_llegada)

    def __str__(self):
        return f"{self.fecha} - {self.zona}"