from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages
from .models import Producto, Zona, RegistroVenta, EnvioInterzona, Jornada, ControlZonaJornada
# Importamos la función actualizada desde tus views
from .views import exportar_excel_jornadas

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)

@admin.register(Zona)
class ZonaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion')
    exclude = ('porcentaje_comision',)   

@admin.register(EnvioInterzona)
class EnvioInterzonaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'zona_origen', 'zona_destino', 'cantidad', 'aceptado')
    list_filter = ('fecha', 'zona_origen', 'zona_destino', 'aceptado')

@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    # Mostramos el acceso al portal y el estado de la jornada
    list_display = ('fecha', 'activa', 'link_del_portal')
    list_editable = ('activa',)
    
    # ACCIÓN PARA GENERAR EL EXCEL CON LAS NUEVAS COLUMNAS
    # actions = ['descargar_reporte_detallado']

    def descargar_reporte_detallado(self, request, queryset):
        # Esta función ahora ejecutará el Excel con: 
        # SALIDA | ENVIO | RECIBIDO | REGRESO | COMISION | etc.
        return exportar_excel_jornadas(request)
    
    descargar_reporte_detallado.short_description = "📊 Exportar Informe (Estructura Solicitada)"

    readonly_fields = ('ver_link_formulario',)
    fields = ('fecha', 'activa', 'ver_link_formulario')

    # --- LÓGICA DE LINKS (COMO LA TENÍAS) ---
    def link_del_portal(self, obj):
        url = "/portal/" 
        return format_html('<a href="{}" target="_blank" style="color: #28a745; font-weight: bold; text-decoration: none;">🚀 Abrir Portal</a>', url)
    link_del_portal.short_description = "Portal de Ventas"

    def ver_link_formulario(self, obj):
        if not obj.pk:
            return "El link aparecerá aquí después de guardar la jornada."
            
        url_vendedores = "http://127.0.0.1:8000/portal/"
        
        return format_html(
            '<div style="background: #f8f9fa; padding: 15px; border: 1px solid #ddd; border-left: 5px solid #28a745;">'
            '<strong>Enlace Único para todos los Vendedores:</strong><br>'
            '<input type="text" value="{}" id="copyLink" style="width: 350px; margin-top: 10px; padding: 8px; border: 1px solid #ccc;" readonly> '
            '<button type="button" onclick="navigator.clipboard.writeText(\'{}\'); alert(\'¡Link copiado!\');" '
            'style="background: #28a745; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; font-weight: bold;">'
            'Copiar Link</button>'
            '</div>',
            url_vendedores, 
            url_vendedores
        )
    ver_link_formulario.short_description = "Configuración de Acceso"


# Mantenemos RegistroVenta por si quieres ver el histórico individual
@admin.register(RegistroVenta)
class RegistroVentaAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'zona', 'producto', 'unidades_vendidas')
    list_filter = ('fecha', 'zona')