# finanzas/admin.py
from django.contrib import admin
from django.contrib.auth.models import Permission
# Importa los modelos desde tu aplicación finanzas
from .models import (
    InstitucionEducativa,
    TipoConceptoPago,
    ConceptoPago,
    CuentaPorCobrarEstudiante,
    PagoRegistrado,
    CuentaContable,
    CategoriaGasto,
    Gasto,
    Proveedor,
    ConsecutivoDocumento,
    AuditoriaExportacionContable,
    WebhookEventoMercadoPago,
    LlamadaMercadoPago,
)   
from gestion_academica.models import EscalaValorativa

from gestion_academica.admin import EscalaValorativaInline 
# --- Clases ModelAdmin (Opcional, pero recomendado para mejor visualización) ---

class EscalaValorativaInline(admin.TabularInline):
    """Permite editar la escala valorativa dentro de la ficha de la institución."""
    model = EscalaValorativa
    extra = 1 # Muestra un campo vacío para añadir una nueva escala.
    ordering = ('orden',)
    fields = ('nombre_desempeno', 'abreviatura', 'nota_minima', 'nota_maxima', 'orden')

class InstitucionEducativaAdmin(admin.ModelAdmin):
    # ¡¡¡AQUÍ ESTÁ LA LÍNEA CORREGIDA!!!
    list_display = ('nombre', 'nit', 'telefono', 'correo_electronico', 'activa') 
    list_filter = ('activa',) # Para poder filtrar por instituciones activas o bloqueadas
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'nit', 'direccion', 'telefono', 'correo_electronico', 'logo', 'eslogan')
        }),
        # --- INICIO: NUEVA SECCIÓN DE CONFIGURACIÓN MAESTRA ---
        ('Configuración de Plataforma (Super-Admin)', {
            'fields': ('activa', 'tipo_institucion', 'tarifa_mensual_plataforma', 'comision_por_transaccion_porcentaje'),
            'classes': ('collapse',),
            'description': 'Estos campos solo deben ser modificados por el super-administrador de HALU.'
        }),
        ('Bilingüismo / Multiidioma', {
            'fields': ('es_bilingue', 'idioma_secundario'),
            'classes': ('collapse',),
            'description': 'Activa esta sección para habilitar campos de segundo idioma en materias y mallas curriculares.',
        }),
        # --- FIN: NUEVA SECCIÓN ---
        ('Información para Boletines', {
            'fields': ('texto_aprobacion', 'texto_resolucion', 'codigo_dane', 'ciudad_departamento', 'nombre_rectora', 'firma_rectora', 'nota_minima_aprobacion')
        }),
        ('Configuración de Pagos', {
            'classes': ('collapse',),
            'fields': (
                'cuenta_bancaria',
                'pagos_digitales',
                'mp_public_key_test',
                'mp_access_token_test',
                'mp_public_key_prod',
                'mp_access_token_prod',
                'mp_modo_produccion',
                'mp_webhook_secret',
            )
        }),
        ('Configuración de Envío de Correo (SMTP)', {
            'classes': ('collapse',),
            'fields': ('email_host_user', 'email_host_password', 'email_host', 'email_port', 'email_use_tls')
        }),
        # --- AÑADE ESTE NUEVO FIELDSET ---
        ('Integraciones Externas', {
            'classes': ('collapse',),
            'fields': (
                'google_calendar_embed_code',
                'google_api_key',
            ),
        }),
        # --- FIN DEL NUEVO FIELDSET ---
    )
    inlines = [EscalaValorativaInline]

    search_fields = ['nombre', 'nit']
    
    #def has_add_permission(self, request):
        #return not InstitucionEducativa.objects.exists()

class TipoConceptoPagoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)

@admin.register(ConceptoPago)
class ConceptoPagoAdmin(admin.ModelAdmin):
    # ✅ Se elimina 'tipo_de_cobro' de la lista
    list_display = (
        'nombre_concepto',
        'valor',
        'nivel_escolaridad',
        'institucion',
        'flags_uso',
        'permite_mora',
    )

    # ✅ Se elimina 'tipo_de_cobro' de los filtros
    list_filter = ('institucion', 'nivel_escolaridad', 'permite_mora', 'es_pago_inscripcion', 'es_pago_matricula', 'es_pago_pension')
    
    search_fields = ('nombre_concepto',)
    
    # ✅ Se elimina 'tipo_de_cobro' del ordenamiento
    ordering = ('institucion', 'nivel_escolaridad__orden', 'nombre_concepto')

    @admin.display(description='Uso')
    def flags_uso(self, obj):
        partes = []
        if obj.es_pago_inscripcion:
            partes.append('Ins')
        if obj.es_pago_matricula:
            partes.append('Mat')
        if obj.es_pago_pension:
            partes.append('Pen')
        if obj.es_solicitable_por_egresado:
            partes.append('Egr')
        return ' / '.join(partes) if partes else '—'

    autocomplete_fields = ['institucion', 'tipo_concepto', 'periodo_academico_aplicable', 'cuenta_contable', 'nivel_escolaridad']

    # ✅ Se elimina 'tipo_de_cobro' del formulario
    fieldsets = (
        ('Información Principal', {
            'fields': ('institucion', 'nombre_concepto', 'valor', 'nivel_escolaridad')
        }),
        ('Clasificación y Vinculación', {
            'fields': ('tipo_concepto', 'periodo_academico_aplicable')
        }),
        ('Configuración Contable (PUC)', {
            'fields': ('cuenta_contable',)
        }),
        ('Cálculo de Intereses por Mora', {
            'fields': ('permite_mora', 'porcentaje_mora_mensual')
        }),
        ('Configuración para Módulos (Banderas)', {
            'fields': (
                'es_pago_inscripcion',
                'es_pago_matricula',
                'es_pago_pension',
                'es_solicitable_por_egresado',
                'automatico',
            ),
            'classes': ('collapse',)
        })
    )

class CuentaPorCobrarEstudianteAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'estudiante', 'concepto_pago', 'monto_asignado', 'monto_pagado_actual', 'saldo_pendiente', 'fecha_vencimiento_especifica', 'estado', 'institucion')
    search_fields = ('estudiante__usuario__username', 'estudiante__codigo_estudiante', 'concepto_pago__nombre_concepto')
    list_filter = ('estado', 'concepto_pago__tipo_concepto', 'fecha_vencimiento_especifica', 'institucion')
    readonly_fields = ('fecha_creacion', 'ultima_modificacion', 'monto_pagado_actual', 'saldo_pendiente')

class PagoRegistradoAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'estudiante', 'cuenta', 'fecha_pago', 'valor_pagado', 'metodo_pago', 'registrado_por', 'institucion')
    search_fields = ('estudiante__usuario__username', 'cuenta__concepto_pago__nombre_concepto', 'referencia_transaccion') 
    list_filter = ('metodo_pago', 'fecha_pago', 'institucion')
    raw_id_fields = ('cuenta', 'estudiante', 'registrado_por')
    readonly_fields = ('fecha_registro_sistema',)

@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = ('numero_documento', 'descripcion', 'monto', 'fecha_gasto', 'categoria', 'institucion')
    list_filter = ('institucion', 'categoria', 'fecha_gasto')
    search_fields = ('descripcion', 'proveedor__nombre')
    autocomplete_fields = ('categoria', 'proveedor')    

@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'cuenta_contable', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)
    autocomplete_fields = ['cuenta_contable'] 

@admin.register(CuentaContable)
class CuentaContableAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('tipo',)    

@admin.register(ConsecutivoDocumento)
class ConsecutivoDocumentoAdmin(admin.ModelAdmin):
    list_display = ('institucion', 'tipo_documento', 'siguiente_numero')
    list_filter = ('institucion', 'tipo_documento')

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nit_o_cedula', 'institucion')
    search_fields = ('nombre', 'nit_o_cedula')
    list_filter = ('institucion',)


@admin.register(AuditoriaExportacionContable)
class AuditoriaExportacionContableAdmin(admin.ModelAdmin):
    list_display = (
        "creado",
        "institucion",
        "usuario",
        "fecha_inicio",
        "fecha_fin",
        "tipo_transaccion",
        "formato",
        "registros",
        "periodo_academico",
    )
    list_filter = ("institucion", "formato", "tipo_transaccion")
    date_hierarchy = "creado"
    readonly_fields = (
        "institucion",
        "usuario",
        "creado",
        "fecha_inicio",
        "fecha_fin",
        "tipo_transaccion",
        "formato",
        "periodo_academico",
        "registros",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WebhookEventoMercadoPago)
class WebhookEventoMercadoPagoAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_recepcion", "institucion", "tipo", "data_id",
        "firma_valida", "estado_http_devuelto", "procesado_ok",
    )
    list_filter = ("institucion", "procesado_ok", "firma_valida", "tipo")
    search_fields = ("data_id", "x_request_id", "payload_hash")
    readonly_fields = (
        "institucion", "data_id", "tipo", "payload_hash",
        "x_request_id", "x_signature", "firma_valida",
        "payload_resumen", "estado_http_devuelto", "procesado_ok",
        "error_mensaje", "pago_registrado", "cuenta",
        "fecha_recepcion", "fecha_procesamiento",
    )
    date_hierarchy = "fecha_recepcion"

    def has_add_permission(self, request):
        return False


@admin.register(LlamadaMercadoPago)
class LlamadaMercadoPagoAdmin(admin.ModelAdmin):
    list_display = (
        "fecha", "institucion", "accion", "intento",
        "estado_http", "exito", "latencia_ms",
        "external_reference", "monto", "modo_produccion",
    )
    list_filter = ("institucion", "accion", "exito", "modo_produccion")
    search_fields = ("external_reference", "error_mensaje")
    readonly_fields = (
        "institucion", "accion", "external_reference", "monto", "cuenta",
        "intento", "latencia_ms", "estado_http", "exito",
        "error_mensaje", "request_resumen", "response_resumen",
        "modo_produccion", "fecha",
    )
    date_hierarchy = "fecha"

    def has_add_permission(self, request):
        return False


# --- Registro de los modelos en el panel de administración ---
admin.site.register(InstitucionEducativa, InstitucionEducativaAdmin)
admin.site.register(TipoConceptoPago, TipoConceptoPagoAdmin)
admin.site.register(CuentaPorCobrarEstudiante, CuentaPorCobrarEstudianteAdmin)
admin.site.register(PagoRegistrado, PagoRegistradoAdmin)
admin.site.register(Permission)


# --- EjecucionHealthCheck (auditoría del dashboard de mantenimiento) ---
from .models import EjecucionHealthCheck


@admin.register(EjecucionHealthCheck)
class EjecucionHealthCheckAdmin(admin.ModelAdmin):
    list_display = (
        "id", "iniciado_at", "iniciado_por", "institucion_filtro",
        "estado", "errores_count", "warnings_count", "pasos_completados",
        "_duracion",
    )
    list_filter = ("estado", "institucion_filtro")
    readonly_fields = (
        "iniciado_at", "terminado_at", "task_id", "iniciado_por",
        "institucion_filtro", "estado", "errores_count", "warnings_count",
        "pasos_completados", "eventos", "error_excepcion",
    )
    date_hierarchy = "iniciado_at"

    def has_add_permission(self, request):
        return False

    def _duracion(self, obj):
        return f"{obj.duracion_segundos}s" if obj.duracion_segundos is not None else "—"
    _duracion.short_description = "Duración"
