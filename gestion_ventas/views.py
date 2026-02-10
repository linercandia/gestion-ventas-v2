"""
Módulo de Vistas - Sistema de Gestión de Ventas
-----------------------------------------------
Este archivo contiene la lógica central del negocio, incluyendo:
1. Gestión de sesiones de vendedores mediante UUID.
2. Integración con Google Sheets API para reportes en tiempo real.
3. Control de inventario interzonas (envíos y recibos).
4. Generación de reportes consolidados en formato Excel.
"""

import os
from decimal import Decimal
import openpyxl
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from django.db import models, IntegrityError
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse

from .models import (
    Jornada, Zona, Producto, EnvioInterzona, 
    ControlZonaJornada, InventarioControl
)

# =============================================================================
# FUNCIONES AUXILIARES (UTILITIES)
# =============================================================================

def sincronizar_a_sheets(tipo, instancia, nombre_vendedor=None):
    """
    Sincroniza los movimientos de la jornada hacia una hoja de cálculo de Google.
    
    Args:
        tipo (str): El tipo de registro ('movimientos', 'confirmacion_interzona', 'dinero').
        instancia (obj): Instancia del modelo (ControlZonaJornada o EnvioInterzona).
        nombre_vendedor (str, optional): Nombre del vendedor para trazabilidad en traspasos.
        
    Estructura de Columnas en Sheets:
    FECHA | NOMBRE | ZONA | PRODUCTO | CANT SALIDA | CANT ENVIADO | CANT RECIBIDO | CANT CIERRE
    """
    try:
        # Configuración de credenciales de Google API
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_path, 'credenciales.json')
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("Registro Ventas")
        sheet_movs = spreadsheet.worksheet("movimientos")

        # Registro de Carga Inicial (Salida de Bodega)
        if tipo == 'movimientos':
            for det in instancia.detalles.all():
                sheet_movs.append_row([
                    str(instancia.jornada.fecha), instancia.nombre_vendedor, instancia.zona.nombre,
                    det.producto.nombre, det.cantidad_salida, 0, 0, 0
                ])

        # Registro de Traspaso entre Zonas (Solo al confirmar recibo)
        elif tipo == 'confirmacion_interzona':
            # Fila 1: Descuento técnico de la zona origen
            sheet_movs.append_row([
                str(instancia.jornada.fecha), instancia.jornada.controlzonajornada_set.filter(zona=instancia.zona_origen).first().nombre_vendedor,
                instancia.zona_origen.nombre, instancia.producto.nombre, 
                0, instancia.cantidad, 0, 0
            ])
            # Fila 2: Ingreso real a la zona destino con nombre del vendedor receptor
            sheet_movs.append_row([
                str(instancia.jornada.fecha), nombre_vendedor, 
                instancia.zona_destino.nombre, instancia.producto.nombre, 
                0, 0, instancia.cantidad, 0
            ])

        # Registro de Cierre de Jornada y Liquidación de Efectivo
        elif tipo == 'dinero':
            sheet_dinero = spreadsheet.worksheet("dinero_entregado")
            sheet_dinero.append_row([
                str(instancia.jornada.fecha), instancia.nombre_vendedor, 
                instancia.zona.nombre, float(instancia.dinero_entregado)
            ])
            for d in instancia.detalles.all():
                sheet_movs.append_row([
                    str(instancia.jornada.fecha), instancia.nombre_vendedor, instancia.zona.nombre,
                    d.producto.nombre, 0, 0, 0, d.cantidad_llegada
                ])
        return True
    except Exception as e:
        # Log de error en consola para debugging técnico
        print(f"Error en sincronización de Google Sheets: {e}")
        return False


# =============================================================================
# VISTAS DEL PORTAL (VIEWS)
# =============================================================================

def portal_vendedor(request):
    """
    Punto de entrada para vendedores. Maneja el flujo de trabajo diario:
    inicio de sesión en zona, envío/recepción de mercancía y cierre.
    """
    hoy = timezone.now().date()
    # Recuperar jornada global configurada por el administrador
    jornada = Jornada.objects.filter(fecha=hoy, activa=True).first()

    # Si no hay jornada activa, se limpia la sesión y se muestra estado inactivo
    if not jornada:
        if 'control_id' in request.session:
            del request.session['control_id']
        return render(request, 'gestion_ventas/portal.html', {'jornada': None})

    # Recuperar el control específico de este vendedor desde la sesión del navegador
    control_id = request.session.get('control_id')
    control = ControlZonaJornada.objects.filter(id=control_id, jornada=jornada).first() if control_id else None

    # Si el vendedor ya cerró su jornada, mostrar resumen de solo lectura
    if control and control.cerrada:
        return render(request, 'gestion_ventas/portal.html', {'control': control, 'jornada': jornada})

    # Procesamiento de Acciones (POST)
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        # ACCIÓN: Registro de Carga Inicial
        if accion == 'registrar_salida':
            zona_id = request.POST.get('zona')
            nombre_v = request.POST.get('nombre_vendedor_input')
            zona = Zona.objects.get(id=zona_id)
            
            control = ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor=nombre_v)
            request.session['control_id'] = control.id # Persistencia de sesión
            
            # Inicializar inventario para cada producto registrado
            for p in Producto.objects.all():
                val = request.POST.get(f'prod_salida_{p.id}', '0').replace('.', '')
                InventarioControl.objects.create(control=control, producto=p, cantidad_salida=int(val) if val else 0)
            
            sincronizar_a_sheets('movimientos', control)
            return redirect('portal_vendedor')

        # ACCIÓN: Envío de mercancía a otra zona
        elif accion == 'enviar_producto' and control:
            destino_id = request.POST.get('zona_destino')
            prod_id = request.POST.get('producto_id')
            cant = int(request.POST.get('cant_envio', '0').replace('.', ''))
            
            if cant > 0 and destino_id:
                # El registro se crea como pendiente (aceptado=False)
                EnvioInterzona.objects.create(
                    jornada=jornada, zona_origen=control.zona, zona_destino_id=destino_id,
                    producto_id=prod_id, cantidad=cant, aceptado=False
                )
            return redirect('portal_vendedor')

        # ACCIÓN: Confirmación de recepción de mercancía
        elif accion == 'confirmar_recibo' and control:
            envio_id = request.POST.get('envio_id')
            envio = EnvioInterzona.objects.get(id=envio_id)
            envio.aceptado = True
            envio.save()
            # Sincronización oficial a Sheets al existir mutuo acuerdo
            sincronizar_a_sheets('confirmacion_interzona', envio, nombre_vendedor=control.nombre_vendedor)
            return redirect('portal_vendedor')

        # ACCIÓN: Cierre final de jornada (Liquidación de inventario y efectivo)
        elif accion == 'cerrar_jornada' and control:
            v_dinero = request.POST.get('dinero_entregado', '0').replace('$', '').replace('.', '').strip()
            control.dinero_entregado = Decimal(v_dinero) if v_dinero else Decimal('0')
            
            for d in control.detalles.all():
                v_llegada = request.POST.get(f'prod_llegada_{d.producto.id}', '0').replace('.', '')
                d.cantidad_llegada = int(v_llegada) if v_llegada else 0
                d.save()
            
            control.cerrada = True
            control.save()
            sincronizar_a_sheets('dinero', control)
            del request.session['control_id'] # Finalizar sesión del navegador
            return render(request, 'gestion_ventas/portal.html', {'control': control, 'jornada': jornada})

    # Preparación del contexto para la interfaz de usuario
    ocupadas = ControlZonaJornada.objects.filter(jornada=jornada).values_list('zona_id', flat=True)
    context = {
        'jornada': jornada, 
        'control': control, 
        'productos': Producto.objects.all(),
        'zonas_disponibles': Zona.objects.exclude(id__in=ocupadas),
        'todas_las_zonas': Zona.objects.exclude(id=control.zona.id) if control else Zona.objects.all(),
    }

    # Carga de datos de trazabilidad para visualización en pantalla
    if control:
        qs = EnvioInterzona.objects.filter(jornada=jornada)
        context.update({
            'envios_realizados': qs.filter(zona_origen=control.zona),
            'envios_pendientes': qs.filter(zona_destino=control.zona, aceptado=False),
            'envios_recibidos_totales': qs.filter(zona_destino=control.zona, aceptado=True),
        })

    return render(request, 'gestion_ventas/portal.html', context)


def pagina_gracias(request):
    """Vista de cortesía al finalizar una sesión."""
    return render(request, 'gestion_ventas/gracias.html')


# =============================================================================
# REPORTES Y EXPORTACIÓN (EXCEL)
# =============================================================================

def exportar_excel_jornadas(request):
    """
    Genera y descarga un archivo .xlsx con el resumen histórico de todas las jornadas.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte General Ventas"
    
    # Encabezados del reporte
    ws.append(['FECHA', 'VENDEDOR', 'ZONA', 'PRODUCTO', 'SALIDA', 'ENVIADO', 'RECIBIDO', 'REGRESO'])
    
    # Consulta optimizada para evitar múltiples accesos a BD
    controles = ControlZonaJornada.objects.all().select_related('jornada', 'zona').prefetch_related('detalles')
    
    for ctrl in controles:
        for det in ctrl.detalles.all():
            ws.append([
                ctrl.jornada.fecha.strftime('%d/%m/%Y'), 
                ctrl.nombre_vendedor, 
                ctrl.zona.nombre, 
                det.producto.nombre, 
                det.cantidad_salida, 
                0, 0, # Estos campos se calculan en RegistroVenta o lógica adicional
                det.cantidad_llegada
            ])
            
    # Configuración de la respuesta HTTP para descarga de archivos
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=ventas_totales.xlsx'
    wb.save(response)
    return response