"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from gestion_ventas import views 
#urls generados
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.panel_cliente, name='panel_cliente'),
    path('panel/', views.panel_cliente, name='panel_cliente'),
    path('panel/jornadas/', views.jornadas_cliente, name='jornadas_cliente'),
    path('panel/jornadas/nueva/', views.jornada_crear, name='jornada_crear'),
    path('panel/jornadas/<int:jornada_id>/editar/', views.jornada_editar, name='jornada_editar'),
    path('panel/zonas/', views.zonas_cliente, name='zonas_cliente'),
    path('panel/productos/', views.productos_cliente, name='productos_cliente'),
    path('panel/vendedores/', views.vendedores_cliente, name='vendedores_cliente'),
    path('panel/adelantos/', views.adelantos_cliente, name='adelantos_cliente'),
    path('panel/pagos/', views.pagos_cliente, name='pagos_cliente'),
    path('panel/pagos/desprendible/', views.desprendible_pago, name='desprendible_pago'),
    path('panel/envios/', views.envios_trazabilidad, name='envios_trazabilidad'),
    path('panel/informes/', views.informes_cliente, name='informes_cliente'),
    path('panel/informes/<int:control_id>/editar/', views.informe_editar, name='informe_editar'),
    path('portal/', views.portal_vendedor, name='portal_vendedor'),
    path('portal/<uuid:token>/', views.portal_vendedor, name='portal_vendedor_token'),
    path('gracias/', views.pagina_gracias, name='pagina_gracias'),
]
