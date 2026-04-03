from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Adelanto,
    Cliente,
    ControlZonaJornada,
    EnvioInterzona,
    Jornada,
    Producto,
    RegistroVenta,
    Vendedor,
    Zona,
)
from .views import exportar_excel_jornadas


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nombre_comercial", "telefono", "activo")
    search_fields = ("usuario__username", "nombre_comercial", "telefono")
    list_filter = ("activo",)


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cliente", "zona_preferida", "telefono", "activo")
    list_filter = ("activo", "cliente", "zona_preferida")
    search_fields = ("nombre", "telefono", "identificacion")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cliente", "codigo", "unidad_medida", "precio_venta", "activo")
    list_filter = ("cliente", "activo", "unidad_medida", "formato_visual")
    search_fields = ("nombre", "codigo")


@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cliente", "codigo", "porcentaje_comision", "activa")
    list_filter = ("cliente", "activa")
    search_fields = ("nombre", "codigo", "descripcion")


@admin.register(EnvioInterzona)
class EnvioInterzonaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "jornada", "producto", "zona_origen", "zona_destino", "cantidad", "aceptado")
    list_filter = ("fecha", "aceptado", "zona_origen", "zona_destino", "jornada")
    search_fields = ("producto__nombre", "zona_origen__nombre", "zona_destino__nombre")


@admin.register(ControlZonaJornada)
class ControlZonaJornadaAdmin(admin.ModelAdmin):
    list_display = ("jornada", "zona", "vendedor_nombre", "cerrada", "dinero_entregado", "pago_neto")
    list_filter = ("cerrada", "jornada", "zona")
    search_fields = ("nombre_vendedor", "vendedor__nombre", "zona__nombre")


@admin.register(Adelanto)
class AdelantoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "vendedor", "control", "monto", "motivo")
    list_filter = ("fecha", "vendedor")
    search_fields = ("vendedor__nombre", "motivo")


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "nombre", "cliente", "activa", "link_del_portal")
    list_filter = ("activa", "cliente", "fecha")
    search_fields = ("nombre", "cliente__nombre_comercial", "cliente__usuario__username")
    readonly_fields = ("ver_link_formulario", "access_token")
    fields = ("cliente", "nombre", "fecha", "activa", "access_token", "ver_link_formulario")
    actions = ["descargar_reporte_detallado"]

    def descargar_reporte_detallado(self, request, queryset):
        return exportar_excel_jornadas(request)

    descargar_reporte_detallado.short_description = "Exportar informe consolidado"

    def link_del_portal(self, obj):
        return format_html(
            '<a href="{}" target="_blank" style="font-weight: 600;">Abrir portal</a>',
            obj.portal_path,
        )

    link_del_portal.short_description = "Portal de ventas"

    def ver_link_formulario(self, obj):
        if not obj.pk:
            return "El enlace se genera después de guardar la jornada."

        return format_html(
            '<div style="padding: 12px; border: 1px solid #d6d6d6; border-left: 4px solid #0d6efd;">'
            "<strong>Enlace para vendedores</strong><br>"
            '<input type="text" value="{}" id="copyLink" style="width: 420px; margin-top: 10px; padding: 8px;" readonly> '
            '<button type="button" onclick="navigator.clipboard.writeText(\'{}\'); alert(\'Link copiado\');" '
            'style="background: #0d6efd; color: white; border: none; padding: 8px 12px; border-radius: 4px; cursor: pointer;">'
            "Copiar</button>"
            '<p style="margin: 10px 0 0; color: #666;">Comparte este enlace con los vendedores para registrar la jornada en tiempo real.</p>'
            "</div>",
            obj.portal_path,
            obj.portal_path,
        )

    ver_link_formulario.short_description = "Acceso del portal"


@admin.register(RegistroVenta)
class RegistroVentaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "jornada", "zona", "producto", "unidades_vendidas")
    list_filter = ("fecha", "jornada", "zona")
    search_fields = ("zona__nombre", "producto__nombre")
