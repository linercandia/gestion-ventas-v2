from django.db import models, IntegrityError
from django.db.models import Sum
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Jornada, Zona, Producto, EnvioInterzona, ControlZonaJornada, InventarioControl
from django.contrib import messages
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from decimal import Decimal
import openpyxl
from django.http import HttpResponse

# --- FUNCIÓN AUXILIAR DE GOOGLE SHEETS ---
def sincronizar_a_sheets(tipo, instancia, nombre_vendedor=None):
    """
    Sincroniza datos a Google Sheets. 
    Columnas: FECHA | NOMBRE | ZONA | PRODUCTO | CANT SALIDA | CANT ENVIADO | CANT RECIBIDO | CANT CIERRE
    """
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_path, 'credenciales.json')
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("Registro Ventas")
        sheet_movs = spreadsheet.worksheet("movimientos")

        if tipo == 'movimientos':
            for det in instancia.detalles.all():
                sheet_movs.append_row([
                    str(instancia.jornada.fecha), instancia.nombre_vendedor, instancia.zona.nombre,
                    det.producto.nombre, det.cantidad_salida, 0, 0, 0
                ])

        elif tipo == 'confirmacion_interzona':
            # 1. Fila de quien ENVIÓ (Salida técnica)
            sheet_movs.append_row([
                str(instancia.jornada.fecha), f"Envío de {instancia.zona_origen.nombre}", 
                instancia.zona_origen.nombre, instancia.producto.nombre, 
                0, instancia.cantidad, 0, 0
            ])
            # 2. Fila de quien RECIBIÓ (Entrada con nombre real)
            sheet_movs.append_row([
                str(instancia.jornada.fecha), nombre_vendedor, 
                instancia.zona_destino.nombre, instancia.producto.nombre, 
                0, 0, instancia.cantidad, 0
            ])

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
        print(f"Error Sheets: {e}")
        return False

# --- VISTA PRINCIPAL ---
def portal_vendedor(request):
    hoy = timezone.now().date()
    jornada = Jornada.objects.filter(fecha=hoy, activa=True).first()

    if not jornada:
        if 'control_id' in request.session:
            del request.session['control_id']
        return render(request, 'gestion_ventas/portal.html', {'jornada': None})

    control_id = request.session.get('control_id')
    control = ControlZonaJornada.objects.filter(id=control_id, jornada=jornada).first() if control_id else None

    if control and control.cerrada:
        return render(request, 'gestion_ventas/portal.html', {'control': control, 'jornada': jornada})

    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        if accion == 'registrar_salida':
            zona_id = request.POST.get('zona')
            nombre_v = request.POST.get('nombre_vendedor_input')
            zona = Zona.objects.get(id=zona_id)
            
            control = ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor=nombre_v)
            request.session['control_id'] = control.id
            
            for p in Producto.objects.all():
                val = request.POST.get(f'prod_salida_{p.id}', '0').replace('.', '')
                InventarioControl.objects.create(control=control, producto=p, cantidad_salida=int(val) if val else 0)
            
            sincronizar_a_sheets('movimientos', control)
            return redirect('portal_vendedor')

        elif accion == 'enviar_producto' and control:
            destino_id = request.POST.get('zona_destino')
            prod_id = request.POST.get('producto_id')
            cant = int(request.POST.get('cant_envio', '0').replace('.', ''))
            
            if cant > 0 and destino_id:
                # Se guarda en BD pero NO en Sheets hasta que se confirme
                EnvioInterzona.objects.create(
                    jornada=jornada, zona_origen=control.zona, zona_destino_id=destino_id,
                    producto_id=prod_id, cantidad=cant, aceptado=False
                )
            return redirect('portal_vendedor')

        elif accion == 'confirmar_recibo' and control:
            envio_id = request.POST.get('envio_id')
            envio = EnvioInterzona.objects.get(id=envio_id)
            envio.aceptado = True
            envio.save()
            # Sincroniza al confirmar
            sincronizar_a_sheets('confirmacion_interzona', envio, nombre_vendedor=control.nombre_vendedor)
            return redirect('portal_vendedor')

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
            del request.session['control_id']
            return render(request, 'gestion_ventas/portal.html', {'control': control, 'jornada': jornada})

    # CONTEXTO PARA VISUALIZACIÓN EN PANTALLA
    ocupadas = ControlZonaJornada.objects.filter(jornada=jornada).values_list('zona_id', flat=True)
    context = {
        'jornada': jornada, 'control': control, 'productos': Producto.objects.all(),
        'zonas_disponibles': Zona.objects.exclude(id__in=ocupadas),
        'todas_las_zonas': Zona.objects.exclude(id=control.zona.id) if control else Zona.objects.all(),
    }
    if control:
        qs = EnvioInterzona.objects.filter(jornada=jornada)
        context.update({
            'envios_realizados': qs.filter(zona_origen=control.zona),
            'envios_pendientes': qs.filter(zona_destino=control.zona, aceptado=False),
            'envios_recibidos_totales': qs.filter(zona_destino=control.zona, aceptado=True),
        })
    return render(request, 'gestion_ventas/portal.html', context)

def pagina_gracias(request):
    return render(request, 'gestion_ventas/gracias.html')

# --- ESTA ES LA FUNCIÓN QUE FALTABA ---
def exportar_excel_jornadas(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['FECHA', 'VENDEDOR', 'ZONA', 'PRODUCTO', 'SALIDA', 'ENVIADO', 'RECIBIDO', 'REGRESO'])
    
    controles = ControlZonaJornada.objects.all().select_related('jornada', 'zona')
    for ctrl in controles:
        for det in ctrl.detalles.all():
            ws.append([
                ctrl.jornada.fecha.strftime('%d/%m/%Y'), 
                ctrl.nombre_vendedor, 
                ctrl.zona.nombre, 
                det.producto.nombre, 
                det.cantidad_salida, 
                0, 0, 
                det.cantidad_llegada
            ])
            
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=ventas_totales.xlsx'
    wb.save(response)
    return response