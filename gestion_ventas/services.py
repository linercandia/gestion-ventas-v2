import os

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from .models import Jornada, Producto, Zona


def obtener_jornada_portal(token=None, fecha=None, cliente=None):
    filtros = {"fecha": fecha, "activa": True} if fecha else {"activa": True}
    if cliente is not None:
        filtros["cliente"] = cliente
    queryset = Jornada.objects.select_related("cliente").filter(**filtros)

    if token:
        return queryset.filter(access_token=token).first()

    return queryset.first()


def productos_disponibles_para_jornada(jornada):
    queryset = Producto.objects.filter(activo=True)
    if jornada and jornada.cliente_id:
        queryset = queryset.filter(cliente=jornada.cliente)
    return queryset


def zonas_disponibles_para_jornada(jornada):
    queryset = Zona.objects.filter(activa=True)
    if jornada and jornada.cliente_id:
        queryset = queryset.filter(cliente=jornada.cliente)
    return queryset


def sincronizar_a_sheets(tipo, instancia, nombre_vendedor=None):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_path, "creds.json")

        creds = ServiceAccountCredentials.from_json_keyfile_name(json_path, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open("Registro Ventas")
        sheet_movs = spreadsheet.worksheet("movimientos")

        if tipo == "movimientos":
            for det in instancia.detalles.all():
                sheet_movs.append_row([
                    str(instancia.jornada.fecha),
                    instancia.vendedor_nombre,
                    instancia.zona.nombre,
                    det.producto.nombre,
                    det.cantidad_salida,
                    0,
                    0,
                    0,
                ])

        elif tipo == "confirmacion_interzona":
            control_origen = instancia.jornada.controlzonajornada_set.filter(zona=instancia.zona_origen).first()
            sheet_movs.append_row([
                str(instancia.jornada.fecha),
                control_origen.vendedor_nombre if control_origen else "",
                instancia.zona_origen.nombre,
                instancia.producto.nombre,
                0,
                instancia.cantidad,
                0,
                0,
            ])
            sheet_movs.append_row([
                str(instancia.jornada.fecha),
                nombre_vendedor,
                instancia.zona_destino.nombre,
                instancia.producto.nombre,
                0,
                0,
                instancia.cantidad,
                0,
            ])

        elif tipo == "dinero":
            sheet_dinero = spreadsheet.worksheet("dinero_entregado")
            sheet_dinero.append_row([
                str(instancia.jornada.fecha),
                instancia.vendedor_nombre,
                instancia.zona.nombre,
                float(instancia.dinero_entregado),
            ])
            for detalle in instancia.detalles.all():
                sheet_movs.append_row([
                    str(instancia.jornada.fecha),
                    instancia.vendedor_nombre,
                    instancia.zona.nombre,
                    detalle.producto.nombre,
                    0,
                    0,
                    0,
                    detalle.cantidad_llegada,
                ])
        return True
    except Exception as exc:
        print(f"Error en sincronizacion de Google Sheets: {exc}")
        return False
