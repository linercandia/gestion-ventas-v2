from datetime import timedelta
from decimal import Decimal

import openpyxl
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.db.models import Sum
from django.forms import modelformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
    AdelantoForm,
    DesprendiblePagoForm,
    InformeForm,
    JornadaForm,
    ProductoForm,
    VendedorForm,
    ZonaForm,
    ZonaProductoComisionFormSet,
)
from .models import Adelanto, ControlZonaJornada, EnvioInterzona, InventarioControl, Producto, Vendedor, Zona, ZonaProductoComision
from .services import (
    obtener_jornada_portal,
    productos_disponibles_para_jornada,
    sincronizar_a_sheets,
    zonas_disponibles_para_jornada,
)


def login_view(request):
    if request.user.is_authenticated:
        return redirect_usuario_segun_rol(request.user)

    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect_usuario_segun_rol(user)
        error = "Credenciales incorrectas. Intenta nuevamente."

    return render(request, "gestion_ventas/login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")


def redirect_usuario_segun_rol(user):
    if user.is_superuser:
        return redirect("/admin/")
    return redirect("panel_cliente")


def obtener_cliente_usuario(request):
    if not request.user.is_authenticated or request.user.is_superuser:
        return None
    return getattr(request.user, "cliente_profile", None)


def obtener_contexto_negocio(cliente):
    return {
        "zonas_qs": cliente.zonas.order_by("nombre"),
        "productos_qs": cliente.productos.order_by("nombre"),
        "vendedores_qs": cliente.vendedores.order_by("nombre"),
    }


def construir_formset_comisiones(productos, data=None, zona=None):
    initial = []
    comisiones_existentes = {}
    if zona is not None:
        comisiones_existentes = {
            comision.producto_id: comision.porcentaje_comision
            for comision in zona.comisiones_producto.select_related("producto").all()
        }
    for producto in productos:
        initial.append(
            {
                "producto_id": producto.id,
                "producto_nombre": producto.nombre,
                "porcentaje_comision": comisiones_existentes.get(producto.id, 0),
            }
        )
    return ZonaProductoComisionFormSet(data=data, initial=initial)


def guardar_comisiones_zona(zona, formset):
    for form in formset:
        producto_id = form.cleaned_data.get("producto_id")
        porcentaje = form.cleaned_data.get("porcentaje_comision")
        if not producto_id or porcentaje is None:
            continue
        ZonaProductoComision.objects.update_or_create(
            zona=zona,
            producto_id=producto_id,
            defaults={"porcentaje_comision": porcentaje},
        )


def panel_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    hoy = timezone.localdate()
    jornadas = cliente.jornadas.order_by("-fecha")[:8]
    controles = (
        ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor")
        .filter(jornada__cliente=cliente)
        .order_by("-jornada__fecha", "zona__nombre")
    )
    context = {
        "cliente": cliente,
        "jornadas": jornadas,
        "jornada_activa": cliente.jornadas.filter(fecha=hoy, activa=True).first(),
        "total_vendedores": cliente.vendedores.filter(activo=True).count(),
        "total_zonas": cliente.zonas.filter(activa=True).count(),
        "total_productos": cliente.productos.filter(activo=True).count(),
        "adelantos_mes": Adelanto.objects.filter(vendedor__cliente=cliente, fecha__month=hoy.month, fecha__year=hoy.year)
        .aggregate(total=Sum("monto"))["total"]
        or 0,
        "ultimos_controles": controles[:10],
    }
    return render(request, "gestion_ventas/panel_cliente.html", context)


def jornadas_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    jornadas = cliente.jornadas.order_by("-fecha", "-id")
    return render(request, "gestion_ventas/jornadas_lista.html", {"cliente": cliente, "jornadas": jornadas})


def jornada_crear(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    form = JornadaForm(request.POST or None, initial={"fecha": timezone.localdate(), "activa": True})
    if request.method == "POST" and form.is_valid():
        jornada = form.save(commit=False)
        jornada.cliente = cliente
        jornada.save()
        messages.success(request, "La jornada se creó correctamente.")
        return redirect("jornadas_cliente")

    return render(
        request,
        "gestion_ventas/jornada_form.html",
        {"cliente": cliente, "form": form, "titulo": "Nueva jornada"},
    )


def jornada_editar(request, jornada_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    jornada = get_object_or_404(cliente.jornadas, id=jornada_id)
    form = JornadaForm(request.POST or None, instance=jornada)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La jornada fue actualizada.")
        return redirect("jornadas_cliente")

    return render(
        request,
        "gestion_ventas/jornada_form.html",
        {"cliente": cliente, "form": form, "titulo": "Editar jornada", "jornada": jornada},
    )


def informes_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    controles = (
        ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor")
        .filter(jornada__cliente=cliente)
        .order_by("-jornada__fecha", "zona__nombre")
    )
    return render(request, "gestion_ventas/informes_lista.html", {"cliente": cliente, "controles": controles})


def zonas_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    zonas = cliente.zonas.prefetch_related("comisiones_producto__producto").order_by("nombre")
    productos = cliente.productos.order_by("nombre")
    form = ZonaForm(request.POST or None)
    formset = construir_formset_comisiones(productos, request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        zona = form.save(commit=False)
        zona.cliente = cliente
        zona.save()
        guardar_comisiones_zona(zona, formset)
        messages.success(request, "La zona fue registrada.")
        return redirect("zonas_cliente")

    return render(
        request,
        "gestion_ventas/zonas_lista.html",
        {"cliente": cliente, "zonas": zonas, "form": form, "formset": formset, "modo": "crear"},
    )


def productos_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    productos = cliente.productos.order_by("nombre")
    form = ProductoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        producto = form.save(commit=False)
        producto.cliente = cliente
        producto.save()
        messages.success(request, "El producto fue registrado.")
        return redirect("productos_cliente")

    return render(
        request,
        "gestion_ventas/productos_lista.html",
        {"cliente": cliente, "productos": productos, "form": form, "modo": "crear"},
    )


def vendedores_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    zonas = cliente.zonas.order_by("nombre")
    vendedores = cliente.vendedores.select_related("zona_preferida").order_by("nombre")
    form = VendedorForm(request.POST or None, zonas=zonas)
    if request.method == "POST" and form.is_valid():
        vendedor = form.save(commit=False)
        vendedor.cliente = cliente
        vendedor.save()
        messages.success(request, "El vendedor fue registrado.")
        return redirect("vendedores_cliente")

    return render(
        request,
        "gestion_ventas/vendedores_lista.html",
        {"cliente": cliente, "vendedores": vendedores, "form": form, "modo": "crear"},
    )


def producto_editar(request, producto_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    producto = get_object_or_404(cliente.productos, id=producto_id)
    form = ProductoForm(request.POST or None, instance=producto)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El producto fue actualizado.")
        return redirect("productos_cliente")

    return render(
        request,
        "gestion_ventas/productos_lista.html",
        {
            "cliente": cliente,
            "productos": cliente.productos.order_by("nombre"),
            "form": form,
            "modo": "editar",
            "objeto_edicion": producto,
        },
    )


def producto_eliminar(request, producto_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    producto = get_object_or_404(cliente.productos, id=producto_id)
    if request.method == "POST":
        producto.delete()
        messages.success(request, "El producto fue eliminado.")
    return redirect("productos_cliente")


def vendedor_editar(request, vendedor_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    vendedor = get_object_or_404(cliente.vendedores, id=vendedor_id)
    zonas = cliente.zonas.order_by("nombre")
    form = VendedorForm(request.POST or None, instance=vendedor, zonas=zonas)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El vendedor fue actualizado.")
        return redirect("vendedores_cliente")

    return render(
        request,
        "gestion_ventas/vendedores_lista.html",
        {
            "cliente": cliente,
            "vendedores": cliente.vendedores.select_related("zona_preferida").order_by("nombre"),
            "form": form,
            "modo": "editar",
            "objeto_edicion": vendedor,
        },
    )


def vendedor_eliminar(request, vendedor_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    vendedor = get_object_or_404(cliente.vendedores, id=vendedor_id)
    if request.method == "POST":
        vendedor.delete()
        messages.success(request, "El vendedor fue eliminado.")
    return redirect("vendedores_cliente")


def zona_editar(request, zona_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    zona = get_object_or_404(cliente.zonas, id=zona_id)
    productos = cliente.productos.order_by("nombre")
    form = ZonaForm(request.POST or None, instance=zona)
    formset = construir_formset_comisiones(productos, request.POST or None, zona=zona)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        guardar_comisiones_zona(zona, formset)
        messages.success(request, "La zona fue actualizada.")
        return redirect("zonas_cliente")

    return render(
        request,
        "gestion_ventas/zonas_lista.html",
        {
            "cliente": cliente,
            "zonas": cliente.zonas.prefetch_related("comisiones_producto__producto").order_by("nombre"),
            "form": form,
            "formset": formset,
            "modo": "editar",
            "objeto_edicion": zona,
        },
    )


def zona_eliminar(request, zona_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    zona = get_object_or_404(cliente.zonas, id=zona_id)
    if request.method == "POST":
        zona.delete()
        messages.success(request, "La zona fue eliminada.")
    return redirect("zonas_cliente")


def adelantos_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    vendedores = cliente.vendedores.order_by("nombre")
    controles = ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor").filter(
        jornada__cliente=cliente
    )
    adelantos = Adelanto.objects.select_related("vendedor", "control__jornada", "control__zona").filter(
        vendedor__cliente=cliente
    )
    form = AdelantoForm(
        request.POST or None,
        vendedores=vendedores,
        controles=controles,
        initial={"fecha": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El adelanto fue registrado.")
        return redirect("adelantos_cliente")

    return render(
        request,
        "gestion_ventas/adelantos_lista.html",
        {"cliente": cliente, "adelantos": adelantos, "form": form},
    )


def pagos_cliente(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    controles = (
        ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor")
        .prefetch_related("detalles__producto", "adelantos")
        .filter(jornada__cliente=cliente, cerrada=True)
        .order_by("-jornada__fecha", "zona__nombre")
    )
    return render(request, "gestion_ventas/pagos_lista.html", {"cliente": cliente, "controles": controles})


def envios_trazabilidad(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    envios = (
        EnvioInterzona.objects.select_related("jornada", "producto", "zona_origen", "zona_destino")
        .filter(jornada__cliente=cliente)
        .order_by("-fecha")
    )
    return render(request, "gestion_ventas/envios_trazabilidad.html", {"cliente": cliente, "envios": envios})


def desprendible_pago(request):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    vendedores = cliente.vendedores.filter(activo=True).order_by("nombre")
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    form = DesprendiblePagoForm(
        request.GET or None,
        vendedores=vendedores,
        initial={"fecha_inicio": inicio_mes, "fecha_fin": hoy},
    )

    controles = ControlZonaJornada.objects.none()
    adelantos_adicionales = Adelanto.objects.none()
    filas_diarias = []
    resumen = None

    if form.is_valid():
        vendedor = form.cleaned_data.get("vendedor")
        fecha_inicio = form.cleaned_data.get("fecha_inicio") or inicio_mes
        fecha_fin = form.cleaned_data.get("fecha_fin") or hoy

        controles = (
            ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor")
            .prefetch_related("detalles__producto", "adelantos")
            .filter(
                jornada__cliente=cliente,
                cerrada=True,
                jornada__fecha__gte=fecha_inicio,
                jornada__fecha__lte=fecha_fin,
            )
            .order_by("jornada__fecha", "zona__nombre")
        )
        if vendedor:
            controles = controles.filter(vendedor=vendedor)

        adelantos_adicionales = Adelanto.objects.filter(
            vendedor__cliente=cliente,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
            control__isnull=True,
        ).order_by("fecha")
        if vendedor:
            adelantos_adicionales = adelantos_adicionales.filter(vendedor=vendedor)

        total_venta = sum(control.total_venta_esperada for control in controles)
        total_enviado = sum(control.total_enviado_valorizado for control in controles)
        total_regreso = sum(control.total_regreso_valorizado for control in controles)
        total_venta_real = sum(control.venta_real for control in controles)
        total_comision = sum(control.comision_valor for control in controles)
        total_descuadre = sum(control.descuadre_dinero for control in controles)
        total_adelantos_vinculados = sum(control.total_adelantos for control in controles)
        total_adelantos_adicionales = adelantos_adicionales.aggregate(total=Sum("monto"))["total"] or Decimal("0")
        total_pagar = total_comision - total_descuadre - total_adelantos_vinculados - total_adelantos_adicionales
        if total_pagar < 0:
            total_pagar = Decimal("0")

        controles_por_fecha = {}
        for control in controles:
            controles_por_fecha.setdefault(control.jornada.fecha, []).append(control)

        adelantos_extra_por_fecha = {}
        for adelanto in adelantos_adicionales:
            adelantos_extra_por_fecha.setdefault(adelanto.fecha, []).append(adelanto)

        fecha_cursor = fecha_fin
        while fecha_cursor >= fecha_inicio:
            controles_dia = controles_por_fecha.get(fecha_cursor, [])
            adelantos_extra_dia = adelantos_extra_por_fecha.get(fecha_cursor, [])
            venta_dia = sum(control.total_venta_esperada for control in controles_dia)
            comision_dia = sum(control.comision_valor for control in controles_dia)
            descuadre_dia = sum(control.descuadre_dinero for control in controles_dia)
            adelantos_jornada_dia = sum(control.total_adelantos for control in controles_dia)
            adelantos_extra_total_dia = sum(adelanto.monto for adelanto in adelantos_extra_dia)
            pago_dia = comision_dia - descuadre_dia - adelantos_jornada_dia - adelantos_extra_total_dia
            if pago_dia < 0:
                pago_dia = Decimal("0")

            filas_diarias.append(
                {
                    "fecha": fecha_cursor,
                    "trabajo": bool(controles_dia),
                    "zonas": ", ".join(control.zona.nombre for control in controles_dia) or "-",
                    "venta": venta_dia,
                    "enviado": sum(control.total_enviado_valorizado for control in controles_dia),
                    "regreso": sum(control.total_regreso_valorizado for control in controles_dia),
                    "venta_real": sum(control.venta_real for control in controles_dia),
                    "comision": comision_dia,
                    "descuadre": descuadre_dia,
                    "adelantos_jornada": adelantos_jornada_dia,
                    "adelantos_extra": adelantos_extra_total_dia,
                    "pago": pago_dia,
                    "controles": controles_dia,
                }
            )
            fecha_cursor -= timedelta(days=1)

        resumen = {
            "vendedor": vendedor,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "total_venta": total_venta,
            "total_enviado": total_enviado,
            "total_regreso": total_regreso,
            "total_venta_real": total_venta_real,
            "total_comision": total_comision,
            "total_descuadre": total_descuadre,
            "total_adelantos_vinculados": total_adelantos_vinculados,
            "total_adelantos_adicionales": total_adelantos_adicionales,
            "total_pagar": total_pagar,
        }

    return render(
        request,
        "gestion_ventas/desprendible_pago.html",
        {
            "cliente": cliente,
            "form": form,
            "controles": controles,
            "adelantos_adicionales": adelantos_adicionales,
            "filas_diarias": filas_diarias,
            "resumen": resumen,
        },
    )


def informe_editar(request, control_id):
    cliente = obtener_cliente_usuario(request)
    if cliente is None:
        return redirect("login")

    control = get_object_or_404(
        ControlZonaJornada.objects.select_related("jornada", "zona", "vendedor").prefetch_related("detalles__producto"),
        id=control_id,
        jornada__cliente=cliente,
    )
    form = InformeForm(request.POST or None, instance=control)
    DetalleFormSet = modelformset_factory(
        InventarioControl,
        fields=("cantidad_salida", "cantidad_llegada"),
        extra=0,
    )
    formset = DetalleFormSet(request.POST or None, queryset=control.detalles.select_related("producto"))

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        form.save()
        formset.save()
        messages.success(request, "El informe fue actualizado.")
        return redirect("informes_cliente")

    return render(
        request,
        "gestion_ventas/informe_form.html",
        {"cliente": cliente, "control": control, "form": form, "formset": formset},
    )


def portal_vendedor(request, token=None):
    hoy = timezone.localdate()
    if token is None and not request.user.is_authenticated:
        return redirect("login")

    cliente = getattr(request.user, "cliente_profile", None) if request.user.is_authenticated else None
    jornada = obtener_jornada_portal(token=token, fecha=hoy, cliente=cliente if token is None else None)

    if not jornada:
        request.session.pop("control_id", None)
        return render(request, "gestion_ventas/portal.html", {"jornada": None})

    control_id = request.session.get("control_id")
    control = (
        ControlZonaJornada.objects.select_related("zona", "vendedor", "jornada")
        .prefetch_related("detalles__producto")
        .filter(id=control_id, jornada=jornada)
        .first()
        if control_id
        else None
    )

    if control and control.cerrada:
        return render(request, "gestion_ventas/portal.html", {"control": control, "jornada": jornada})

    productos = productos_disponibles_para_jornada(jornada)
    zonas = zonas_disponibles_para_jornada(jornada)
    vendedores = Vendedor.objects.filter(cliente=jornada.cliente, activo=True) if jornada.cliente_id else Vendedor.objects.none()

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "registrar_salida":
            zona_id = request.POST.get("zona")
            nombre_vendedor = request.POST.get("nombre_vendedor_input", "").strip()
            vendedor_id = request.POST.get("vendedor")

            zona = zonas.get(id=zona_id)
            vendedor = vendedores.filter(id=vendedor_id).first() if vendedor_id else None
            nombre_registrado = vendedor.nombre if vendedor else nombre_vendedor

            control = ControlZonaJornada.objects.create(
                jornada=jornada,
                zona=zona,
                vendedor=vendedor,
                nombre_vendedor=nombre_registrado,
            )
            request.session["control_id"] = control.id

            for producto in productos:
                valor = request.POST.get(f"prod_salida_{producto.id}", "0").replace(".", "")
                InventarioControl.objects.create(
                    control=control,
                    producto=producto,
                    cantidad_salida=int(valor) if valor else 0,
                )

            sincronizar_a_sheets("movimientos", control)
            return redirect(request.path)

        if accion == "enviar_producto" and control:
            destino_id = request.POST.get("zona_destino")
            producto_id = request.POST.get("producto_id")
            cantidad = int(request.POST.get("cant_envio", "0").replace(".", ""))

            if cantidad > 0 and destino_id and str(control.zona_id) != str(destino_id):
                EnvioInterzona.objects.create(
                    jornada=jornada,
                    zona_origen=control.zona,
                    zona_destino_id=destino_id,
                    producto_id=producto_id,
                    cantidad=cantidad,
                    aceptado=False,
                )
            else:
                messages.error(request, "El envio debe tener cantidad valida y una zona destino diferente.")
            return redirect(request.path)

        if accion == "confirmar_recibo" and control:
            envio_id = request.POST.get("envio_id")
            envio = get_object_or_404(
                EnvioInterzona,
                id=envio_id,
                jornada=jornada,
                zona_destino=control.zona,
                aceptado=False,
            )
            envio.aceptado = True
            envio.save(update_fields=["aceptado"])
            sincronizar_a_sheets("confirmacion_interzona", envio, nombre_vendedor=control.vendedor_nombre)
            return redirect(request.path)

        if accion == "rechazar_recibo" and control:
            envio_id = request.POST.get("envio_id")
            envio = get_object_or_404(
                EnvioInterzona,
                id=envio_id,
                jornada=jornada,
                zona_destino=control.zona,
                aceptado=False,
            )
            envio.delete()
            messages.warning(request, "El envio fue rechazado.")
            return redirect(request.path)

        if accion == "cerrar_jornada" and control:
            valor_dinero = request.POST.get("dinero_entregado", "0").replace("$", "").replace(".", "").strip()
            control.dinero_entregado = Decimal(valor_dinero) if valor_dinero else Decimal("0")

            for detalle in control.detalles.all():
                valor_llegada = request.POST.get(f"prod_llegada_{detalle.producto.id}", "0").replace(".", "")
                detalle.cantidad_llegada = int(valor_llegada) if valor_llegada else 0
                detalle.save(update_fields=["cantidad_llegada"])

            control.cerrada = True
            control.save(update_fields=["dinero_entregado", "cerrada"])
            sincronizar_a_sheets("dinero", control)
            request.session.pop("control_id", None)
            return render(request, "gestion_ventas/portal.html", {"control": control, "jornada": jornada})

    ocupadas = ControlZonaJornada.objects.filter(jornada=jornada).values_list("zona_id", flat=True)
    zonas_configuradas = zonas
    context = {
        "jornada": jornada,
        "control": control,
        "productos": productos,
        "vendedores": vendedores,
        "zonas_disponibles": zonas.exclude(id__in=ocupadas),
        "zonas_configuradas": zonas_configuradas,
        "zonas_ocupadas_ids": list(ocupadas),
        "todas_las_zonas": zonas.exclude(id=control.zona.id) if control else zonas,
    }

    if control:
        envios = EnvioInterzona.objects.filter(jornada=jornada)
        context.update(
            {
                "envios_realizados": envios.filter(zona_origen=control.zona),
                "envios_pendientes": envios.filter(zona_destino=control.zona, aceptado=False),
                "envios_recibidos_totales": envios.filter(zona_destino=control.zona, aceptado=True),
            }
        )

    return render(request, "gestion_ventas/portal.html", context)


def pagina_gracias(request):
    return render(request, "gestion_ventas/gracias.html")


def exportar_excel_jornadas(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte General Ventas"
    ws.append(
        [
            "FECHA",
            "CLIENTE",
            "VENDEDOR",
            "ZONA",
            "PRODUCTO",
            "SALIDA",
            "ENVIADO",
            "RECIBIDO",
            "REGRESO",
            "VENDIDO",
            "PRECIO",
            "VENTA ESPERADA PRODUCTO",
            "COMISION %",
            "DINERO ENTREGADO",
            "ADELANTOS",
            "DESCUADRE",
            "PAGO NETO",
        ]
    )

    controles = (
        ControlZonaJornada.objects.select_related("jornada__cliente", "zona", "vendedor")
        .prefetch_related("detalles__producto")
        .all()
    )

    for control in controles:
        for detalle in control.detalles.all():
            enviados = (
                EnvioInterzona.objects.filter(
                    jornada=control.jornada,
                    zona_origen=control.zona,
                    producto=detalle.producto,
                    aceptado=True,
                ).aggregate(total=Sum("cantidad"))["total"]
                or 0
            )
            recibidos = (
                EnvioInterzona.objects.filter(
                    jornada=control.jornada,
                    zona_destino=control.zona,
                    producto=detalle.producto,
                    aceptado=True,
                ).aggregate(total=Sum("cantidad"))["total"]
                or 0
            )
            vendido = (detalle.cantidad_salida + recibidos) - (enviados + detalle.cantidad_llegada)
            ws.append(
                [
                    control.jornada.fecha.strftime("%d/%m/%Y"),
                    str(control.jornada.cliente) if control.jornada.cliente_id else "General",
                    control.vendedor_nombre,
                    control.zona.nombre,
                    detalle.producto.nombre,
                    detalle.cantidad_salida,
                    enviados,
                    recibidos,
                    detalle.cantidad_llegada,
                    vendido,
                    detalle.producto.precio_venta,
                    vendido * detalle.producto.precio_venta,
                    control.zona.get_porcentaje_comision_producto(detalle.producto),
                    control.dinero_entregado,
                    control.total_adelantos,
                    control.descuadre_dinero,
                    control.pago_neto,
                ]
            )

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=ventas_totales.xlsx"
    wb.save(response)
    return response
