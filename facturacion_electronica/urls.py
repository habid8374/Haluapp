from django.urls import path

from . import views

app_name = "facturacion_electronica"

urlpatterns = [
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/probar/", views.probar_conexion, name="probar_conexion"),
    path("facturas/", views.lista_facturas, name="lista_facturas"),
    path("facturas/<int:factura_id>/", views.detalle_factura, name="detalle_factura"),
    path("emitir/<int:pago_id>/", views.emitir_factura, name="emitir_factura"),
    path("nota-credito/<int:factura_id>/", views.emitir_nota_credito, name="emitir_nota_credito"),
    path("nota-debito/<int:factura_id>/", views.emitir_nota_debito, name="emitir_nota_debito"),
]
