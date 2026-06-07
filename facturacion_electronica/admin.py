from django.contrib import admin

from .models import ConfiguracionFactus, FacturaElectronica


@admin.register(ConfiguracionFactus)
class ConfiguracionFactusAdmin(admin.ModelAdmin):
    list_display = ("institucion", "ambiente", "activo", "facturas_emitidas", "fecha_actualizacion")
    list_filter = ("activo", "ambiente")
    search_fields = ("institucion__nombre",)
    # 'activo' editable solo desde aquí (propietario) — es el interruptor del adicional.
    readonly_fields = ("facturas_emitidas", "fecha_creacion", "fecha_actualizacion")


@admin.register(FacturaElectronica)
class FacturaElectronicaAdmin(admin.ModelAdmin):
    list_display = ("reference_code", "institucion", "estado", "numero", "fecha_creacion")
    list_filter = ("estado", "ambiente", "institucion")
    search_fields = ("reference_code", "numero", "cufe")
    readonly_fields = ("fecha_creacion", "fecha_validacion", "json_enviado", "json_respuesta")
