import uuid

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Cliente(TimeStampedModel):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cliente_profile",
    )
    nombre_comercial = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return self.nombre_comercial or self.usuario.get_username()


class Producto(models.Model):
    UNIDADES = [
        ("Lb", "Libra"),
        ("Und", "Unidad"),
    ]
    FORMATOS = [
        ("moneda", "Pesos Colombianos ($)"),
        ("unidades", "Unidades (Puntos de mil)"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="productos",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=30, blank=True)
    unidad_medida = models.CharField(max_length=5, choices=UNIDADES, default="Und")
    formato_visual = models.CharField(
        max_length=10,
        choices=FORMATOS,
        default="unidades",
        verbose_name="Formato de ingreso",
    )
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        # La forma de captura se deriva de la unidad elegida.
        self.formato_visual = "unidades" if self.unidad_medida == "Und" else "moneda"
        super().save(*args, **kwargs)

    @property
    def formato_captura(self):
        return "unidades" if self.unidad_medida == "Und" else "moneda"

    def __str__(self):
        return self.nombre


class Zona(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="zonas",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=100)
    codigo = models.CharField(max_length=30, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Zona"
        verbose_name_plural = "Zonas"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.porcentaje_comision}%)"

    def get_porcentaje_comision_producto(self, producto):
        relacion = self.comisiones_producto.filter(producto=producto).first()
        if relacion:
            return relacion.porcentaje_comision
        return 0


class ZonaProductoComision(models.Model):
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE, related_name="comisiones_producto")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="comisiones_zona")
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Comision por producto en zona"
        verbose_name_plural = "Comisiones por producto en zona"
        constraints = [
            models.UniqueConstraint(fields=["zona", "producto"], name="unique_comision_producto_por_zona")
        ]
        ordering = ["producto__nombre"]

    def __str__(self):
        return f"{self.zona.nombre} - {self.producto.nombre} ({self.porcentaje_comision}%)"


class Vendedor(TimeStampedModel):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="vendedores")
    nombre = models.CharField(max_length=100)
    telefono = models.CharField(max_length=30, blank=True)
    identificacion = models.CharField(max_length=30, blank=True)
    zona_preferida = models.ForeignKey(
        Zona,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="vendedores_preferidos",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Jornada(models.Model):
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="jornadas",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=150, blank=True)
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha de la Jornada")
    activa = models.BooleanField(default=True)
    access_token = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    class Meta:
        verbose_name = "Jornada"
        verbose_name_plural = "Jornadas"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["cliente", "fecha"], name="unique_jornada_por_cliente_y_fecha")
        ]

    @property
    def portal_path(self):
        return reverse("portal_vendedor_token", args=[self.access_token])

    @property
    def portal_url(self):
        return f"{settings.APP_BASE_URL}{self.portal_path}"

    def __str__(self):
        nombre = f" - {self.nombre}" if self.nombre else ""
        return f"Jornada {self.fecha}{nombre}"


class ControlZonaJornada(models.Model):
    id_sesion = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    jornada = models.ForeignKey(Jornada, on_delete=models.CASCADE)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE)
    vendedor = models.ForeignKey(
        Vendedor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="controles",
    )
    cerrada = models.BooleanField(default=False, verbose_name="¿Cerró Jornada?")
    nombre_vendedor = models.CharField(max_length=100, blank=True, null=True)
    dinero_entregado = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    class Meta:
        unique_together = ("jornada", "zona")
        verbose_name = "Control de Zona"
        verbose_name_plural = "Controles de Zonas"
        ordering = ["-jornada__fecha", "zona__nombre"]

    @property
    def vendedor_nombre(self):
        if self.vendedor_id:
            return self.vendedor.nombre
        return self.nombre_vendedor or "Sin vendedor"

    def cantidad_enviada_producto(self, producto):
        return (
            EnvioInterzona.objects.filter(
                jornada=self.jornada,
                zona_origen=self.zona,
                producto=producto,
                aceptado=True,
            ).aggregate(total=Sum("cantidad"))["total"]
            or 0
        )

    def cantidad_recibida_producto(self, producto):
        return (
            EnvioInterzona.objects.filter(
                jornada=self.jornada,
                zona_destino=self.zona,
                producto=producto,
                aceptado=True,
            ).aggregate(total=Sum("cantidad"))["total"]
            or 0
        )

    def unidades_vendidas_producto(self, detalle):
        return (detalle.cantidad_salida + self.cantidad_recibida_producto(detalle.producto)) - (
            self.cantidad_enviada_producto(detalle.producto) + detalle.cantidad_llegada
        )

    def valor_salida_producto(self, detalle):
        return detalle.cantidad_salida * detalle.producto.precio_venta

    def valor_recibido_producto(self, detalle):
        return self.cantidad_recibida_producto(detalle.producto) * detalle.producto.precio_venta

    def valor_enviado_producto(self, detalle):
        return self.cantidad_enviada_producto(detalle.producto) * detalle.producto.precio_venta

    def valor_regreso_producto(self, detalle):
        return detalle.cantidad_llegada * detalle.producto.precio_venta

    @property
    def total_salida_valorizada(self):
        return sum(self.valor_salida_producto(detalle) for detalle in self.detalles.select_related("producto").all())

    @property
    def total_recibido_valorizado(self):
        return sum(self.valor_recibido_producto(detalle) for detalle in self.detalles.select_related("producto").all())

    @property
    def total_enviado_valorizado(self):
        return sum(self.valor_enviado_producto(detalle) for detalle in self.detalles.select_related("producto").all())

    @property
    def total_regreso_valorizado(self):
        return sum(self.valor_regreso_producto(detalle) for detalle in self.detalles.select_related("producto").all())

    @property
    def total_venta_esperada(self):
        return self.total_salida_valorizada + self.total_recibido_valorizado

    @property
    def total_venta_objetivo(self):
        total = self.total_venta_esperada - self.total_enviado_valorizado - self.total_regreso_valorizado
        return total if total > 0 else 0

    @property
    def venta_real(self):
        return self.dinero_entregado

    @property
    def comision_porcentaje(self):
        return self.zona.porcentaje_comision

    @property
    def comision_valor(self):
        total = 0
        for detalle in self.detalles.select_related("producto").all():
            venta_producto = self.unidades_vendidas_producto(detalle) * detalle.producto.precio_venta
            porcentaje = self.zona.get_porcentaje_comision_producto(detalle.producto)
            total += (venta_producto * porcentaje) / 100
        return total

    @property
    def total_adelantos(self):
        return self.adelantos.aggregate(total=Sum("monto"))["total"] or 0

    @property
    def descuadre_dinero(self):
        diferencia = self.total_venta_objetivo - self.venta_real
        return diferencia if diferencia > 0 else 0

    @property
    def pago_neto(self):
        pago = self.comision_valor - self.total_adelantos - self.descuadre_dinero
        return pago if pago > 0 else 0

    @property
    def rentabilidad(self):
        rentabilidad = self.venta_real - self.comision_valor
        return rentabilidad if rentabilidad > 0 else 0

    def __str__(self):
        estado = "Cerrada" if self.cerrada else "Abierta"
        return f"{self.zona.nombre} - {self.jornada.fecha} ({estado})"


class InventarioControl(models.Model):
    control = models.ForeignKey(ControlZonaJornada, on_delete=models.CASCADE, related_name="detalles")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_salida = models.IntegerField(default=0)
    cantidad_llegada = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Inventario de Jornada"
        verbose_name_plural = "Inventarios de Jornada"

    def __str__(self):
        return f"{self.producto.nombre} en {self.control.zona.nombre}"


class EnvioInterzona(models.Model):
    jornada = models.ForeignKey(
        Jornada,
        on_delete=models.CASCADE,
        related_name="envios",
        null=True,
        blank=True,
    )
    fecha = models.DateTimeField(auto_now_add=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    zona_origen = models.ForeignKey(Zona, related_name="envios_salientes", on_delete=models.CASCADE)
    zona_destino = models.ForeignKey(Zona, related_name="envios_entrantes", on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    aceptado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Envío Interzona"
        verbose_name_plural = "Envíos Interzona"
        ordering = ["-fecha"]

    @property
    def vendedor_origen_nombre(self):
        control = ControlZonaJornada.objects.filter(jornada=self.jornada, zona=self.zona_origen).select_related("vendedor").first()
        return control.vendedor_nombre if control else "-"

    @property
    def vendedor_destino_nombre(self):
        control = ControlZonaJornada.objects.filter(jornada=self.jornada, zona=self.zona_destino).select_related("vendedor").first()
        return control.vendedor_nombre if control else "-"

    def __str__(self):
        return f"{self.producto} de {self.zona_origen} a {self.zona_destino}"


class RegistroVenta(models.Model):
    jornada = models.ForeignKey(
        Jornada,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="registros_venta",
    )
    fecha = models.DateField(auto_now_add=True)
    zona = models.ForeignKey(Zona, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad_salida = models.IntegerField(verbose_name="Carga Inicial")
    cantidad_llegada = models.IntegerField(verbose_name="Regresó a Bodega", default=0)

    class Meta:
        verbose_name = "Registro de Venta"
        verbose_name_plural = "Registros de Venta"
        ordering = ["-fecha", "zona__nombre"]

    def unidades_vendidas(self):
        filtros_jornada = {"jornada": self.jornada} if self.jornada_id else {"jornada__fecha": self.fecha}

        recibido = EnvioInterzona.objects.filter(
            zona_destino=self.zona,
            producto=self.producto,
            aceptado=True,
            **filtros_jornada,
        ).aggregate(Sum("cantidad"))["cantidad__sum"] or 0

        entregado = EnvioInterzona.objects.filter(
            zona_origen=self.zona,
            producto=self.producto,
            aceptado=True,
            **filtros_jornada,
        ).aggregate(Sum("cantidad"))["cantidad__sum"] or 0

        return (self.cantidad_salida + recibido) - (entregado + self.cantidad_llegada)

    def __str__(self):
        return f"{self.fecha} - {self.zona}"


class Adelanto(models.Model):
    vendedor = models.ForeignKey(Vendedor, on_delete=models.CASCADE, related_name="adelantos")
    control = models.ForeignKey(
        ControlZonaJornada,
        on_delete=models.CASCADE,
        related_name="adelantos",
        blank=True,
        null=True,
    )
    fecha = models.DateField(default=timezone.now)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "Adelanto"
        verbose_name_plural = "Adelantos"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.vendedor.nombre} - {self.monto}"
