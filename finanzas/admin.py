# finanzas/admin.py
from django import forms
from django.contrib import admin
from django.contrib.auth.models import Permission

from proyecto_colegio.admin_mixins import (
    InstitucionScopedAdminMixin,
    SuperuserOnlyAdminMixin,
)
# Importa los modelos desde tu aplicación finanzas
from .models import (
    InstitucionEducativa,
    ModuloPlataforma,
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
    ConsumoIA,
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

_IDIOMA_INTERFAZ_LABELS = {
    'en': 'English (Inglés)',
    'fr': 'Français (Francés)',
    'pt': 'Português (Portugués)',
    'de': 'Deutsch (Alemán)',
    'zh': '中文 (Mandarín)',
}


class InstitucionEducativaAdminForm(forms.ModelForm):
    """Formulario del admin: los idiomas de interfaz contratados se eligen con
    casillas (checkboxes), no con JSON crudo. Solo se ofrecen los idiomas que ya
    tienen traducción disponible."""
    idiomas_contratados = forms.MultipleChoiceField(
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=[(c, _IDIOMA_INTERFAZ_LABELS.get(c, c))
                 for c in InstitucionEducativa.IDIOMAS_INTERFAZ_DISPONIBLES],
        label="Idiomas de interfaz contratados",
        help_text="Idiomas (además del español, que siempre está) en los que este "
                  "colegio puede ver la plataforma. Aparecen en el selector de idioma "
                  "de sus usuarios.",
    )

    class Meta:
        model = InstitucionEducativa
        fields = '__all__'


class InstitucionEducativaAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    form = InstitucionEducativaAdminForm
    # ¡¡¡AQUÍ ESTÁ LA LÍNEA CORREGIDA!!!
    list_display = ('nombre', 'nit', 'telefono', 'correo_electronico', 'activa')
    list_filter = ('activa',) # Para poder filtrar por instituciones activas o bloqueadas
    autocomplete_fields = ['simat_municipio_etc']
    # Selector de doble lista para marcar los módulos del plan cómodamente.
    filter_horizontal = ('modulos_contratados',)
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'nit', 'direccion', 'telefono', 'correo_electronico', 'logo', 'eslogan')
        }),
        # --- INICIO: NUEVA SECCIÓN DE CONFIGURACIÓN MAESTRA ---
        ('Configuración de Plataforma (Super-Admin)', {
            'fields': ('activa', 'tipo_institucion', 'usa_modulo_financiero', 'tarifa_mensual_plataforma', 'comision_por_transaccion_porcentaje'),
            'classes': ('collapse',),
            'description': 'Estos campos solo deben ser modificados por el super-administrador de HALU.'
        }),
        ('Módulos contratados (plan del colegio)', {
            'fields': ('modulos_contratados',),
            'description': (
                'Marca los módulos que este colegio compró. Los que NO estén '
                'marcados se ocultan del menú y se bloquean para sus usuarios '
                '(el superusuario siempre los ve). El módulo de Finanzas se '
                'controla arriba con «Usa el módulo financiero».'
            ),
        }),
        ('Bilingüismo / Multiidioma', {
            'fields': ('idiomas_contratados', 'es_bilingue', 'idioma_secundario'),
            'classes': ('collapse',),
            'description': (
                '«Idiomas de interfaz contratados»: marca los idiomas (además del '
                'español) en los que este colegio puede ver la plataforma — aparecen '
                'en el selector de idioma de cada usuario. «Es bilingüe» + «Idioma '
                'secundario» son para las materias y mallas bilingües, no para la interfaz.'
            ),
        }),
        # --- FIN: NUEVA SECCIÓN ---
        ('Información para Boletines', {
            'fields': ('texto_aprobacion', 'texto_resolucion', 'codigo_dane', 'ciudad_departamento', 'nombre_rectora', 'firma_rectora', 'nota_minima_aprobacion')
        }),
        ('Reporte SIMAT (MEN)', {
            'classes': ('collapse',),
            'description': 'Datos oficiales para el reporte de matrícula SIMAT. '
                           'El código DANE de la institución se toma de "Información para Boletines". '
                           'Las sedes se administran en SIMAT › Sedes.',
            'fields': ('simat_municipio_etc', 'simat_calendario', 'simat_sector', 'simat_prestacion_servicio', 'simat_consecutivo_sede_automatico'),
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
        ('Configuración de Envío de Correo', {
            'classes': ('collapse',),
            'description': 'Brevo API tiene prioridad sobre SMTP si se configura. SMTP es el canal de respaldo.',
            'fields': (
                'brevo_api_key', 'brevo_sender_email', 'brevo_sender_name',
                'email_host_user', 'email_host_password', 'email_host', 'email_port', 'email_use_tls',
            )
        }),
        # --- AÑADE ESTE NUEVO FIELDSET ---
        ('Integraciones Externas', {
            'classes': ('collapse',),
            'fields': (
                'google_calendar_embed_code',
                'google_api_key',
                'claude_api_key',
            ),
        }),
        ('Inteligencia Artificial — Tope de consumo', {
            'classes': ('collapse',),
            'description': 'Protección de costos: límite mensual de IA (Gemini/Claude) para esta institución.',
            'fields': (
                'ia_tope_mensual_cop',
                'ia_bloquear_al_superar',
            ),
        }),
        # --- FIN DEL NUEVO FIELDSET ---
    )
    inlines = [EscalaValorativaInline]

    search_fields = ['nombre', 'nit']
    
    #def has_add_permission(self, request):
        #return not InstitucionEducativa.objects.exists()

class TipoConceptoPagoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)

@admin.register(ConceptoPago)
class ConceptoPagoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
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

class CuentaPorCobrarEstudianteAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero_documento', 'estudiante', 'concepto_pago', 'monto_asignado', 'monto_pagado_actual', 'saldo_pendiente', 'fecha_vencimiento_especifica', 'estado', 'institucion')
    search_fields = ('estudiante__usuario__username', 'estudiante__codigo_estudiante', 'concepto_pago__nombre_concepto')
    list_filter = ('estado', 'concepto_pago__tipo_concepto', 'fecha_vencimiento_especifica', 'institucion')
    readonly_fields = ('fecha_creacion', 'ultima_modificacion', 'monto_pagado_actual', 'saldo_pendiente')

class PagoRegistradoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero_documento', 'estudiante', 'cuenta', 'fecha_pago', 'valor_pagado', 'metodo_pago', 'registrado_por', 'institucion')
    search_fields = ('estudiante__usuario__username', 'cuenta__concepto_pago__nombre_concepto', 'referencia_transaccion') 
    list_filter = ('metodo_pago', 'fecha_pago', 'institucion')
    raw_id_fields = ('cuenta', 'estudiante', 'registrado_por')
    readonly_fields = ('fecha_registro_sistema',)

@admin.register(Gasto)
class GastoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero_documento', 'descripcion', 'monto', 'fecha_gasto', 'categoria', 'institucion')
    list_filter = ('institucion', 'categoria', 'fecha_gasto')
    search_fields = ('descripcion', 'proveedor__nombre')
    autocomplete_fields = ('categoria', 'proveedor')    

@admin.register(CategoriaGasto)
class CategoriaGastoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'cuenta_contable', 'institucion')
    search_fields = ('nombre',)
    list_filter = ('institucion',)
    autocomplete_fields = ['cuenta_contable'] 

@admin.register(CuentaContable)
class CuentaContableAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo')
    search_fields = ('codigo', 'nombre')
    list_filter = ('tipo',)    

@admin.register(ConsecutivoDocumento)
class ConsecutivoDocumentoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('institucion', 'tipo_documento', 'siguiente_numero')
    list_filter = ('institucion', 'tipo_documento')

@admin.register(Proveedor)
class ProveedorAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'nit_o_cedula', 'institucion')
    search_fields = ('nombre', 'nit_o_cedula')
    list_filter = ('institucion',)


@admin.register(AuditoriaExportacionContable)
class AuditoriaExportacionContableAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
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
class WebhookEventoMercadoPagoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
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
class LlamadaMercadoPagoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
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


class AgregarModuloForm(forms.ModelForm):
    """Formulario de ALTA por desplegable: eliges un módulo conocido y el resto
    de sus datos (código, URL, ícono, descripción) se completan solos."""

    class Meta:
        model = ModuloPlataforma
        fields = ['codigo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from finanzas.modulos import MODULOS_CONOCIDOS
        existentes = set(ModuloPlataforma.objects.values_list('codigo', flat=True))
        opciones = [
            (cod, data['nombre'])
            for cod, data in sorted(MODULOS_CONOCIDOS.items(), key=lambda kv: kv[1].get('orden', 100))
            if cod not in existentes
        ]
        self.fields['codigo'] = forms.ChoiceField(
            label="Módulo a agregar",
            choices=[('', '— Elige un módulo —')] + opciones,
            help_text=("Elige el módulo de la lista (puedes escribir para buscar). "
                       "Su código, URL, ícono y descripción se completan solos al guardar."),
        )
        if not opciones:
            self.fields['codigo'].help_text = "Ya están agregados todos los módulos conocidos."

    def save(self, commit=True):
        from finanzas.modulos import MODULOS_CONOCIDOS
        cod = self.cleaned_data['codigo']
        data = MODULOS_CONOCIDOS[cod]
        obj = super().save(commit=False)
        obj.codigo = cod
        obj.nombre = data['nombre']
        obj.prefijo_url = data.get('prefijo_url', '')
        obj.icono = data.get('icono', '')
        obj.descripcion = data.get('descripcion', '')
        obj.orden = data.get('orden', 100)
        obj.activo = True
        if commit:
            obj.save()
        return obj


class ModuloPlataformaAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Catálogo GLOBAL de módulos de la plataforma (solo el propietario). Para
    AGREGAR: eliges un módulo de un desplegable y todo se rellena solo. Para
    EDITAR: puedes ajustar cualquier campo a mano."""
    list_display = ('nombre', 'codigo', 'prefijo_url', 'orden', 'activo', 'n_instituciones')
    list_editable = ('orden', 'activo')
    search_fields = ('nombre', 'codigo', 'prefijo_url')
    ordering = ('orden', 'nombre')

    @admin.display(description='Colegios con el módulo')
    def n_instituciones(self, obj):
        return obj.instituciones.count()

    def get_form(self, request, obj=None, **kwargs):
        # Al AGREGAR (obj=None) usamos el formulario de desplegable; al editar,
        # el formulario normal con todos los campos.
        if obj is None:
            kwargs['form'] = AgregarModuloForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {
                'fields': ('codigo',),
                'description': ('Elige el módulo que quieres habilitar. El código, la URL, '
                               'el ícono y la descripción se completan automáticamente.'),
            }),)
        return super().get_fieldsets(request, obj)

    def get_prepopulated_fields(self, request, obj=None):
        # Solo al editar tiene sentido autollenar el código desde el nombre.
        if obj is None:
            return {}
        return {'codigo': ('nombre',)}


admin.site.register(ModuloPlataforma, ModuloPlataformaAdmin)
admin.site.register(TipoConceptoPago, TipoConceptoPagoAdmin)
admin.site.register(CuentaPorCobrarEstudiante, CuentaPorCobrarEstudianteAdmin)
admin.site.register(PagoRegistrado, PagoRegistradoAdmin)


class PermissionAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
    """Modelo global de Django sin institución: solo el superusuario."""
    pass


admin.site.register(Permission, PermissionAdmin)


# --- EjecucionHealthCheck (auditoría del dashboard de mantenimiento) ---
from .models import EjecucionHealthCheck


@admin.register(EjecucionHealthCheck)
class EjecucionHealthCheckAdmin(SuperuserOnlyAdminMixin, admin.ModelAdmin):
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


@admin.register(ConsumoIA)
class ConsumoIAAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    """Panel de consumo de IA por institución y mes (medidor del tope)."""
    list_display = ('institucion', 'anio', 'mes', 'operaciones', 'tokens_in', 'tokens_out', 'costo_estimado_cop', 'actualizado')
    list_filter = ('anio', 'mes', 'institucion')
    search_fields = ('institucion__nombre',)
    readonly_fields = ('institucion', 'anio', 'mes', 'operaciones', 'tokens_in', 'tokens_out', 'costo_estimado_cop', 'actualizado')
    ordering = ('-anio', '-mes')

    def has_add_permission(self, request):
        return False
