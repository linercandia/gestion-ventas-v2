from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from datetime import timedelta
from decimal import Decimal
import os
import shutil

from .models import Adelanto, Cliente, ControlZonaJornada, EnvioInterzona, InventarioControl, Jornada, Producto, Vendedor, Zona, ZonaProductoComision
from .templatetags.moneda import cop


User = get_user_model()


class ClienteSignalsTests(TestCase):
    def test_crea_perfil_cliente_al_crear_usuario(self):
        user = User.objects.create_user(username="cliente_demo", password="secret123")

        self.assertTrue(Cliente.objects.filter(usuario=user).exists())

    def test_filtro_cop_formatea_sin_decimales(self):
        self.assertEqual(cop(Decimal("12345.67")), "$ 12.346")
        self.assertEqual(cop(Decimal("-5000")), "-$ 5.000")


class PortalJornadaTests(TestCase):
    def test_portal_publico_resuelve_jornada_por_fecha_y_token(self):
        user = User.objects.create_user(username="cliente_portal_fecha", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)

        response = self.client.get(reverse("portal_vendedor_token_fecha", args=[jornada.fecha.isoformat(), jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jornada"], jornada)

    def test_portal_publico_resuelve_jornada_por_token(self):
        user = User.objects.create_user(username="cliente_portal", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jornada"], jornada)

    def test_jornada_expone_url_absoluta_lista_para_compartir(self):
        user = User.objects.create_user(username="cliente_url", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)

        self.assertTrue(jornada.portal_url.startswith(f"{settings.APP_BASE_URL}/portal/{jornada.fecha.isoformat()}/"))

    def test_portal_publico_muestra_vendedores_del_negocio(self):
        user = User.objects.create_user(username="cliente_vendedores", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="PABLO")

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PABLO")
        self.assertIn(vendedor, response.context["vendedores"])

    def test_portal_avisa_cuando_no_hay_zonas_libres(self):
        user = User.objects.create_user(username="cliente_zonas", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor="Ana")

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay zonas activas libres para esta jornada.")

    def test_portal_muestra_unidad_del_producto(self):
        user = User.objects.create_user(username="cliente_unidad", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unidad: Unidad")
        self.assertContains(response, 'data-formato="unidades"')
        self.assertContains(response, 'accept=".jpg,.jpeg,.png,.webp,.heic,.heif,image/jpeg,image/png,image/webp,image/heic,image/heif"')
        self.assertNotContains(response, 'capture="environment"')

    def test_portal_muestra_pesos_como_doble_signo_para_productos_tipo_libra(self):
        user = User.objects.create_user(username="cliente_pesos", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        Producto.objects.create(cliente=cliente, nombre="Rellena", unidad_medida="Lb", precio_venta=5000)

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$$")
        self.assertContains(response, 'data-formato="moneda"')

    def test_portal_usa_unidad_real_aun_si_formato_guardado_esta_mal(self):
        user = User.objects.create_user(username="cliente_unidad_real", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Envuelto", unidad_medida="Und", precio_venta=1000)
        Producto.objects.filter(id=producto.id).update(formato_visual="moneda")

        response = self.client.get(reverse("portal_vendedor_token", args=[jornada.access_token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-formato="unidades"')

    def test_portal_guarda_foto_de_evidencia_por_producto(self):
        user = User.objects.create_user(username="cliente_foto", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")
        foto = SimpleUploadedFile("evidencia.jpg", b"fake-image-content", content_type="image/jpeg")
        temp_media = os.path.join(settings.BASE_DIR, "test_media_uploads")
        os.makedirs(temp_media, exist_ok=True)

        try:
            with self.settings(MEDIA_ROOT=temp_media):
                response = self.client.post(
                    reverse("portal_vendedor_token", args=[jornada.access_token]),
                    {
                        "accion": "registrar_salida",
                        "zona": str(zona.id),
                        "nombre_vendedor_input": "Ana",
                        f"prod_salida_{producto.id}": "12",
                        f"prod_evidencia_{producto.id}": foto,
                    },
                )
                detalle = InventarioControl.objects.get(control__jornada=jornada, producto=producto)
        finally:
            shutil.rmtree(temp_media, ignore_errors=True)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(detalle.evidencia_salida.name.endswith(".jpg"))

    def test_portal_no_registra_salida_si_falta_una_foto(self):
        user = User.objects.create_user(username="cliente_sin_foto", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")

        response = self.client.post(
            reverse("portal_vendedor_token", args=[jornada.access_token]),
            {
                "accion": "registrar_salida",
                "zona": str(zona.id),
                "nombre_vendedor_input": "Ana",
                f"prod_salida_{producto.id}": "12",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Debes adjuntar una foto de evidencia para cada producto antes de registrar la salida.")
        self.assertFalse(ControlZonaJornada.objects.filter(jornada=jornada, zona=zona).exists())

    def test_envio_se_crea_pendiente_y_se_confirma_en_destino(self):
        user = User.objects.create_user(username="cliente_envio", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona_origen = Zona.objects.create(cliente=cliente, nombre="Norte", activa=True)
        zona_destino = Zona.objects.create(cliente=cliente, nombre="Sur", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")
        control_origen = ControlZonaJornada.objects.create(jornada=jornada, zona=zona_origen, nombre_vendedor="Ana")
        control_destino = ControlZonaJornada.objects.create(jornada=jornada, zona=zona_destino, nombre_vendedor="Luis")
        InventarioControl.objects.create(control=control_origen, producto=producto, cantidad_salida=10)
        InventarioControl.objects.create(control=control_destino, producto=producto, cantidad_salida=0)

        session = self.client.session
        session["control_id"] = control_origen.id
        session.save()
        response_envio = self.client.post(
            reverse("portal_vendedor_token", args=[jornada.access_token]),
            {
                "accion": "enviar_producto",
                "zona_destino": str(zona_destino.id),
                "producto_id": str(producto.id),
                "cant_envio": "3",
            },
        )
        envio = EnvioInterzona.objects.get()

        self.assertEqual(response_envio.status_code, 302)
        self.assertFalse(envio.aceptado)

        session = self.client.session
        session["control_id"] = control_destino.id
        session.save()
        response_confirmacion = self.client.post(
            reverse("portal_vendedor_token", args=[jornada.access_token]),
            {
                "accion": "confirmar_recibo",
                "envio_id": str(envio.id),
            },
        )
        envio.refresh_from_db()

        self.assertEqual(response_confirmacion.status_code, 302)
        self.assertTrue(envio.aceptado)

    def test_envio_puede_rechazarse_desde_zona_destino(self):
        user = User.objects.create_user(username="cliente_rechazo", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona_origen = Zona.objects.create(cliente=cliente, nombre="Norte", activa=True)
        zona_destino = Zona.objects.create(cliente=cliente, nombre="Sur", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")
        ControlZonaJornada.objects.create(jornada=jornada, zona=zona_origen, nombre_vendedor="Ana")
        control_destino = ControlZonaJornada.objects.create(jornada=jornada, zona=zona_destino, nombre_vendedor="Luis")
        envio = EnvioInterzona.objects.create(
            jornada=jornada,
            zona_origen=zona_origen,
            zona_destino=zona_destino,
            producto=producto,
            cantidad=2,
            aceptado=False,
        )

        session = self.client.session
        session["control_id"] = control_destino.id
        session.save()
        response = self.client.post(
            reverse("portal_vendedor_token", args=[jornada.access_token]),
            {
                "accion": "rechazar_recibo",
                "envio_id": str(envio.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EnvioInterzona.objects.filter(id=envio.id).exists())


class PanelClienteTests(TestCase):
    def test_usuario_cliente_autenticado_ve_panel(self):
        user = User.objects.create_user(username="cliente_panel", password="secret123")
        cliente = user.cliente_profile
        self.client.login(username="cliente_panel", password="secret123")

        response = self.client.get(reverse("panel_cliente"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["cliente"], cliente)

    def test_usuarios_comparten_vendedores_entre_perfiles(self):
        owner = User.objects.create_user(username="cliente_owner", password="secret123")
        other = User.objects.create_user(username="cliente_other", password="secret123")
        Vendedor.objects.create(cliente=other.cliente_profile, nombre="Compartido")

        self.client.login(username="cliente_owner", password="secret123")
        response = self.client.get(reverse("vendedores_cliente"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartido")

    def test_superusuario_desde_login_va_al_admin(self):
        User.objects.create_superuser(username="root", password="secret123", email="root@example.com")

        response = self.client.post(
            reverse("login"),
            {"username": "root", "password": "secret123"},
        )

        self.assertRedirects(response, "/admin/")

    def test_cliente_puede_editar_informe_propio(self):
        user = User.objects.create_user(username="cliente_edit", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro")
        control = ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor="Ana")
        self.client.login(username="cliente_edit", password="secret123")

        response = self.client.get(reverse("informe_editar", args=[control.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["control"], control)

    def test_cliente_puede_eliminar_jornada_desde_panel(self):
        user = User.objects.create_user(username="cliente_eliminar_jornada", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)

        self.client.login(username="cliente_eliminar_jornada", password="secret123")
        response = self.client.post(reverse("jornada_eliminar", args=[jornada.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Jornada.objects.filter(id=jornada.id).exists())

    def test_usuario_cliente_puede_registrar_zona_y_producto(self):
        user = User.objects.create_user(username="cliente_catalogo", password="secret123")
        cliente = user.cliente_profile
        Producto.objects.create(cliente=cliente, nombre="Base", unidad_medida="Und", precio_venta=1000)
        self.client.login(username="cliente_catalogo", password="secret123")

        zona_response = self.client.post(
            reverse("zonas_cliente"),
            {
                "nombre": "Norte",
                "codigo": "N1",
                "descripcion": "Zona norte",
                "porcentaje_comision": "12.5",
                "activa": "on",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-producto_id": str(Producto.objects.get(nombre="Base").id),
                "form-0-producto_nombre": "Base",
                "form-0-porcentaje_comision": "15",
            },
        )
        producto_response = self.client.post(
            reverse("productos_cliente"),
            {
                "nombre": "Producto A",
                "codigo": "PA",
                "unidad_medida": "Und",
                "precio_venta": "3000",
                "activo": "on",
            },
        )

        self.assertEqual(zona_response.status_code, 302)
        self.assertEqual(producto_response.status_code, 302)
        self.assertTrue(Zona.objects.filter(nombre="Norte").exists())
        self.assertTrue(Producto.objects.filter(nombre="Producto A", precio_venta=3000).exists())

    def test_zona_guarda_comision_distinta_por_producto(self):
        user = User.objects.create_user(username="cliente_comision_zona", password="secret123")
        cliente = user.cliente_profile
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", unidad_medida="Und", precio_venta=1000)
        self.client.login(username="cliente_comision_zona", password="secret123")

        response = self.client.post(
            reverse("zonas_cliente"),
            {
                "nombre": "Norte",
                "codigo": "N1",
                "descripcion": "Zona norte",
                "porcentaje_comision": "10",
                "activa": "on",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-producto_id": str(producto.id),
                "form-0-producto_nombre": "Producto A",
                "form-0-porcentaje_comision": "18",
            },
        )

        zona = Zona.objects.get(nombre="Norte")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(zona.get_porcentaje_comision_producto(producto), Decimal("18"))
        self.assertTrue(ZonaProductoComision.objects.filter(zona=zona, producto=producto, porcentaje_comision=18).exists())

    def test_resumen_zonas_muestra_producto_y_porcentaje(self):
        user = User.objects.create_user(username="cliente_resumen_zona", password="secret123")
        cliente = user.cliente_profile
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", unidad_medida="Und", precio_venta=1000)
        zona = Zona.objects.create(cliente=cliente, nombre="Norte")
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=22)
        self.client.login(username="cliente_resumen_zona", password="secret123")

        response = self.client.get(reverse("zonas_cliente"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Producto A: 22")

    def test_producto_vendedor_y_zona_se_pueden_editar_y_eliminar(self):
        user = User.objects.create_user(username="cliente_crud", password="secret123")
        cliente = user.cliente_profile
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", unidad_medida="Und", precio_venta=1000)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", porcentaje_comision=10)
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="Pedro", zona_preferida=zona)
        self.client.login(username="cliente_crud", password="secret123")

        response_producto = self.client.post(
            reverse("producto_editar", args=[producto.id]),
            {"nombre": "Producto B", "codigo": "", "unidad_medida": "Lb", "precio_venta": "2000", "activo": "on"},
        )
        response_vendedor = self.client.post(
            reverse("vendedor_editar", args=[vendedor.id]),
            {"nombre": "Pedro Diaz", "telefono": "", "identificacion": "", "zona_preferida": str(zona.id), "activo": "on"},
        )
        response_zona = self.client.post(
            reverse("zona_editar", args=[zona.id]),
            {
                "nombre": "Centro Plus",
                "codigo": "",
                "descripcion": "",
                "porcentaje_comision": "12",
                "activa": "on",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-producto_id": str(producto.id),
                "form-0-producto_nombre": producto.nombre,
                "form-0-porcentaje_comision": "16",
            },
        )

        producto.refresh_from_db()
        vendedor.refresh_from_db()
        zona.refresh_from_db()
        self.assertEqual(response_producto.status_code, 302)
        self.assertEqual(response_vendedor.status_code, 302)
        self.assertEqual(response_zona.status_code, 302)
        self.assertEqual(producto.nombre, "Producto B")
        self.assertEqual(producto.formato_visual, "moneda")
        self.assertEqual(vendedor.nombre, "Pedro Diaz")
        self.assertEqual(zona.nombre, "Centro Plus")
        self.assertEqual(zona.get_porcentaje_comision_producto(producto), Decimal("16"))

        self.client.post(reverse("producto_eliminar", args=[producto.id]))
        self.client.post(reverse("vendedor_eliminar", args=[vendedor.id]))
        self.client.post(reverse("zona_eliminar", args=[zona.id]))
        self.assertFalse(Producto.objects.filter(id=producto.id).exists())
        self.assertFalse(Vendedor.objects.filter(id=vendedor.id).exists())
        self.assertFalse(Zona.objects.filter(id=zona.id).exists())

    def test_producto_define_formato_segun_unidad(self):
        user = User.objects.create_user(username="cliente_formatos", password="secret123")
        cliente = user.cliente_profile

        producto_unidad = Producto.objects.create(cliente=cliente, nombre="Producto U", unidad_medida="Und", precio_venta=1000)
        producto_libra = Producto.objects.create(cliente=cliente, nombre="Producto L", unidad_medida="Lb", precio_venta=5000)

        self.assertEqual(producto_unidad.formato_visual, "unidades")
        self.assertEqual(producto_libra.formato_visual, "moneda")

    def test_panel_muestra_trazabilidad_de_envios(self):
        user = User.objects.create_user(username="cliente_traza", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona_origen = Zona.objects.create(cliente=cliente, nombre="Norte", activa=True)
        zona_destino = Zona.objects.create(cliente=cliente, nombre="Sur", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", precio_venta=1000)
        ControlZonaJornada.objects.create(jornada=jornada, zona=zona_origen, nombre_vendedor="Ana")
        ControlZonaJornada.objects.create(jornada=jornada, zona=zona_destino, nombre_vendedor="Luis")
        EnvioInterzona.objects.create(
            jornada=jornada,
            zona_origen=zona_origen,
            zona_destino=zona_destino,
            producto=producto,
            cantidad=3,
            aceptado=False,
        )
        self.client.login(username="cliente_traza", password="secret123")

        response = self.client.get(reverse("envios_trazabilidad"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")
        self.assertContains(response, "Luis")
        self.assertContains(response, "Pendiente")

    def test_desprendible_pago_filtra_por_vendedor_y_calcula_total(self):
        user = User.objects.create_user(username="cliente_desprendible", password="secret123")
        cliente = user.cliente_profile
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="Pedro")
        otra_vendedora = Vendedor.objects.create(cliente=cliente, nombre="Ana")
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", porcentaje_comision=10)
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", unidad_medida="Und", precio_venta=Decimal("10000"))
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=10)
        fecha_fin = timezone.localdate()
        fecha_inicio = fecha_fin - timedelta(days=2)
        jornada = Jornada.objects.create(cliente=cliente, fecha=fecha_fin, activa=True)
        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            vendedor=vendedor,
            nombre_vendedor="Pedro",
            dinero_entregado=Decimal("35000"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=control, producto=producto, cantidad_salida=5, cantidad_llegada=1)
        Adelanto.objects.create(vendedor=vendedor, control=control, monto=Decimal("1000"))
        Adelanto.objects.create(vendedor=vendedor, monto=Decimal("500"), fecha=timezone.localdate(), motivo="Anticipo")

        otra_jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate() - timedelta(days=1), activa=False)
        otro_control = ControlZonaJornada.objects.create(
            jornada=otra_jornada,
            zona=zona,
            vendedor=otra_vendedora,
            nombre_vendedor="Ana",
            dinero_entregado=Decimal("50000"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=otro_control, producto=producto, cantidad_salida=5, cantidad_llegada=0)

        self.client.login(username="cliente_desprendible", password="secret123")
        response = self.client.get(
            reverse("desprendible_pago"),
            {
                "vendedor": vendedor.id,
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pedro")
        self.assertEqual(list(response.context["controles"]), [control])
        self.assertEqual(len(response.context["filas_diarias"]), 3)
        self.assertEqual(response.context["filas_diarias"][0]["fecha"], fecha_fin)
        self.assertEqual(response.context["filas_diarias"][1]["fecha"], fecha_fin - timedelta(days=1))
        self.assertEqual(response.context["filas_diarias"][2]["fecha"], fecha_inicio)
        self.assertFalse(response.context["filas_diarias"][1]["trabajo"])
        self.assertEqual(response.context["resumen"]["total_base_pago"], Decimal("50000"))
        self.assertEqual(response.context["resumen"]["total_venta"], Decimal("40000"))
        self.assertEqual(response.context["resumen"]["total_venta_real"], Decimal("35000"))
        self.assertEqual(response.context["resumen"]["total_regreso"], Decimal("10000"))
        self.assertEqual(response.context["resumen"]["total_comision"], Decimal("5000"))
        self.assertEqual(response.context["resumen"]["total_descuadre"], Decimal("5000"))
        self.assertEqual(response.context["resumen"]["total_adelantos_vinculados"], Decimal("1000"))
        self.assertEqual(response.context["resumen"]["total_adelantos_adicionales"], Decimal("500"))
        self.assertEqual(response.context["resumen"]["total_pagar"], Decimal("0"))

    def test_pago_neto_descuenta_adelantos_y_descuadre(self):
        user = User.objects.create_user(username="cliente_pago", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", porcentaje_comision=10)
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", precio_venta=Decimal("10000"))
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=10)
        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            nombre_vendedor="Ana",
            dinero_entregado=Decimal("35000"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=control, producto=producto, cantidad_salida=5, cantidad_llegada=1)
        Adelanto.objects.create(vendedor=user.cliente_profile.vendedores.create(nombre="Ana"), control=control, monto=Decimal("2000"))

        self.assertEqual(control.total_base_pago, Decimal("50000"))
        self.assertEqual(control.total_venta_esperada, Decimal("40000"))
        self.assertEqual(control.total_venta_objetivo, Decimal("40000"))
        self.assertEqual(control.venta_real, Decimal("35000"))
        self.assertEqual(control.comision_valor, Decimal("5000"))
        self.assertEqual(control.descuadre_dinero, Decimal("5000"))
        self.assertEqual(control.total_adelantos, Decimal("2000"))
        self.assertEqual(control.rentabilidad, Decimal("35000"))
        self.assertEqual(control.pico, Decimal("-5000"))
        self.assertEqual(control.pago_neto, 0)

    def test_comision_valor_usa_porcentaje_por_producto_en_zona(self):
        user = User.objects.create_user(username="cliente_pago_producto", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", porcentaje_comision=10)
        producto = Producto.objects.create(cliente=cliente, nombre="Producto A", unidad_medida="Und", precio_venta=Decimal("10000"))
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=20)
        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            nombre_vendedor="Ana",
            dinero_entregado=Decimal("40000"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=control, producto=producto, cantidad_salida=5, cantidad_llegada=1)

        self.assertEqual(control.total_venta_esperada, Decimal("40000"))
        self.assertEqual(control.comision_valor, Decimal("10000"))

    def test_producto_en_pesos_no_multiplica_por_precio_venta(self):
        user = User.objects.create_user(username="cliente_pago_pesos", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Porvenir", porcentaje_comision=10)
        producto = Producto.objects.create(
            cliente=cliente,
            nombre="Rellena",
            unidad_medida="Lb",
            precio_venta=Decimal("6000"),
        )
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=38.4)
        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            nombre_vendedor="Pablo",
            dinero_entregado=Decimal("18000"),
            cerrada=True,
        )
        InventarioControl.objects.create(
            control=control,
            producto=producto,
            cantidad_salida=Decimal("60000"),
            cantidad_llegada=Decimal("24000"),
        )

        self.assertEqual(control.total_base_pago, Decimal("60000"))
        self.assertEqual(control.total_venta_esperada, Decimal("36000"))
        self.assertEqual(control.total_venta_objetivo, Decimal("36000"))
        self.assertEqual(control.venta_real, Decimal("18000"))
        self.assertEqual(control.comision_valor, Decimal("23040"))
        self.assertEqual(control.descuadre_dinero, Decimal("18000"))

    def test_informes_filtra_y_muestra_metricas_por_producto(self):
        user = User.objects.create_user(username="cliente_informes", password="secret123")
        cliente = user.cliente_profile
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="Pablo")
        otra_zona = Zona.objects.create(cliente=cliente, nombre="Norte", activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Porvenir", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Rellena", unidad_medida="Lb", precio_venta=Decimal("6000"))
        ZonaProductoComision.objects.create(zona=zona, producto=producto, porcentaje_comision=38.4)
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            vendedor=vendedor,
            nombre_vendedor="Pablo",
            dinero_entregado=Decimal("18000"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=control, producto=producto, cantidad_salida=Decimal("60000"), cantidad_llegada=Decimal("24000"))
        ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=otra_zona,
            nombre_vendedor="Otro",
            dinero_entregado=Decimal("50000"),
            cerrada=True,
        )

        self.client.login(username="cliente_informes", password="secret123")
        response = self.client.get(
            reverse("informes_cliente"),
            {"fecha": timezone.localdate().isoformat(), "vendedor": vendedor.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["filas_informe"]), 1)
        fila = response.context["filas_informe"][0]
        self.assertEqual(fila["salida"], Decimal("60000"))
        self.assertEqual(fila["llegada"], Decimal("24000"))
        self.assertEqual(fila["venta_esperada_producto"], Decimal("36000"))
        self.assertEqual(fila["sueldo"], Decimal("23040"))
        self.assertEqual(fila["producido"], Decimal("12960"))
        self.assertEqual(fila["pico"], Decimal("-23040"))

    def test_informe_filtra_por_fecha_y_vendedor_mostrando_todas_sus_zonas_del_dia(self):
        user = User.objects.create_user(username="cliente_informes_zonas", password="secret123")
        cliente = user.cliente_profile
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="Pedro")
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona_a = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        zona_b = Zona.objects.create(cliente=cliente, nombre="Sur", activa=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")

        control_a = ControlZonaJornada.objects.create(jornada=jornada, zona=zona_a, vendedor=vendedor, nombre_vendedor="Pedro", cerrada=True)
        control_b = ControlZonaJornada.objects.create(jornada=jornada, zona=zona_b, vendedor=vendedor, nombre_vendedor="Pedro", cerrada=True)
        InventarioControl.objects.create(control=control_a, producto=producto, cantidad_salida=10, cantidad_llegada=2)
        InventarioControl.objects.create(control=control_b, producto=producto, cantidad_salida=8, cantidad_llegada=1)

        self.client.login(username="cliente_informes_zonas", password="secret123")
        response = self.client.get(
            reverse("informes_cliente"),
            {"fecha": timezone.localdate().isoformat(), "vendedor": vendedor.id},
        )

        self.assertEqual(response.status_code, 200)
        bloques = response.context["bloques_informe"]
        self.assertEqual(len(bloques), 2)
        zonas = {bloque["zona"] for bloque in bloques}
        self.assertEqual(zonas, {"Centro", "Sur"})

    def test_informe_muestra_producido_por_producto_y_no_total_del_control(self):
        user = User.objects.create_user(username="cliente_informes_multi", password="secret123")
        cliente = user.cliente_profile
        vendedor = Vendedor.objects.create(cliente=cliente, nombre="Pedro")
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)

        producto_a = Producto.objects.create(cliente=cliente, nombre="Envueltos", unidad_medida="Lb", precio_venta=Decimal("1000"))
        producto_b = Producto.objects.create(cliente=cliente, nombre="Rellena", unidad_medida="Lb", precio_venta=Decimal("1000"))
        ZonaProductoComision.objects.create(zona=zona, producto=producto_a, porcentaje_comision=10)
        ZonaProductoComision.objects.create(zona=zona, producto=producto_b, porcentaje_comision=4)

        control = ControlZonaJornada.objects.create(
            jornada=jornada,
            zona=zona,
            vendedor=vendedor,
            nombre_vendedor="Pedro",
            dinero_entregado=Decimal("52800"),
            cerrada=True,
        )
        InventarioControl.objects.create(control=control, producto=producto_a, cantidad_salida=Decimal("6000"), cantidad_llegada=Decimal("1200"))
        InventarioControl.objects.create(control=control, producto=producto_b, cantidad_salida=Decimal("50000"), cantidad_llegada=Decimal("2000"))

        self.client.login(username="cliente_informes_multi", password="secret123")
        response = self.client.get(reverse("informes_cliente"), {"fecha": timezone.localdate().isoformat()})

        self.assertEqual(response.status_code, 200)
        filas = response.context["filas_informe"]
        self.assertEqual(len(filas), 2)
        fila_envueltos = next(fila for fila in filas if fila["producto"].nombre == "Envueltos")
        fila_rellena = next(fila for fila in filas if fila["producto"].nombre == "Rellena")

        self.assertEqual(fila_envueltos["venta_esperada_producto"], Decimal("4800"))
        self.assertEqual(fila_envueltos["sueldo"], Decimal("600"))
        self.assertEqual(fila_envueltos["producido"], Decimal("4200"))

        self.assertEqual(fila_rellena["venta_esperada_producto"], Decimal("48000"))
        self.assertEqual(fila_rellena["sueldo"], Decimal("2000"))
        self.assertEqual(fila_rellena["producido"], Decimal("46000"))

    def test_cliente_puede_eliminar_informe_desde_panel(self):
        user = User.objects.create_user(username="cliente_eliminar_informe", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        control = ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor="Pablo", cerrada=True)

        self.client.login(username="cliente_eliminar_informe", password="secret123")
        response = self.client.post(reverse("informe_eliminar", args=[control.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ControlZonaJornada.objects.filter(id=control.id).exists())

    def test_cliente_puede_ver_fotos_de_salida_desde_informes(self):
        user = User.objects.create_user(username="cliente_fotos_informe", password="secret123")
        cliente = user.cliente_profile
        jornada = Jornada.objects.create(cliente=cliente, fecha=timezone.localdate(), activa=True)
        zona = Zona.objects.create(cliente=cliente, nombre="Centro", activa=True)
        control = ControlZonaJornada.objects.create(jornada=jornada, zona=zona, nombre_vendedor="Pablo", cerrada=True)
        producto = Producto.objects.create(cliente=cliente, nombre="Empanada", unidad_medida="Und", formato_visual="unidades")
        foto = SimpleUploadedFile("salida.jpg", b"fake-image-content", content_type="image/jpeg")
        temp_media = os.path.join(settings.BASE_DIR, "test_media_uploads_informes")
        os.makedirs(temp_media, exist_ok=True)

        try:
            with self.settings(MEDIA_ROOT=temp_media):
                InventarioControl.objects.create(
                    control=control,
                    producto=producto,
                    cantidad_salida=5,
                    evidencia_salida=foto,
                )

                self.client.login(username="cliente_fotos_informe", password="secret123")
                response = self.client.get(reverse("informe_fotos", args=[control.id]))
        finally:
            shutil.rmtree(temp_media, ignore_errors=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Empanada")
        self.assertContains(response, "Abrir foto")
