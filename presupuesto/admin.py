from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import (
    CDP,
    RP,
    Apropiacion,
    CatalogoGeneralCuentas,
    CategoriaCPC,
    ComprobanteContable,
    ConceptoRetencion,
    CuentaBancaria,
    ElementoAlmacen,
    FuenteFinanciacion,
    ModificacionPresupuestal,
    MovimientoAlmacen,
    MovimientoContable,
    MovimientoTesoreria,
    Obligacion,
    OrdenDePago,
    PresupuestoIngreso,
    RetencionAplicada,
    RubroPresupuestalGasto,
    RubroPresupuestalIngreso,
    VigenciaFiscal,
)


@admin.register(VigenciaFiscal)
class VigenciaFiscalAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('institucion', 'anio', 'estado', 'fecha_apertura', 'fecha_cierre')
    list_filter = ('estado',)
    ordering = ('-anio',)
    raw_id_fields = ('institucion',)


@admin.register(RubroPresupuestalIngreso)
class RubroPresupuestalIngresoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo_recurso', 'institucion', 'activo')
    list_filter = ('activo',)
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    raw_id_fields = ('institucion', 'rubro_padre', 'tipo_recurso')


@admin.register(RubroPresupuestalGasto)
class RubroPresupuestalGastoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'cuenta_cgc_gasto', 'institucion', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    raw_id_fields = ('institucion', 'rubro_padre', 'cuenta_cgc_gasto')


@admin.register(PresupuestoIngreso)
class PresupuestoIngresoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('rubro', 'vigencia', 'valor_inicial', 'valor_recaudado', 'institucion')
    list_filter = ('vigencia',)
    ordering = ('-vigencia',)
    raw_id_fields = ('institucion', 'vigencia', 'rubro')


@admin.register(Apropiacion)
class ApropiacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('rubro', 'vigencia', 'valor_inicial', 'valor_definitivo', 'saldo_disponible', 'institucion')
    list_filter = ('vigencia',)
    ordering = ('-vigencia',)
    raw_id_fields = ('institucion', 'vigencia', 'rubro')

    @admin.display(description='Valor definitivo')
    def valor_definitivo(self, obj):
        return f"${obj.valor_definitivo:,.2f}"

    @admin.display(description='Saldo disponible')
    def saldo_disponible(self, obj):
        return f"${obj.saldo_disponible:,.2f}"


@admin.register(ModificacionPresupuestal)
class ModificacionPresupuestalAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('apropiacion', 'tipo', 'valor', 'apropiacion_destino', 'fecha', 'institucion')
    list_filter = ('tipo',)
    ordering = ('-fecha',)
    raw_id_fields = ('institucion', 'apropiacion', 'apropiacion_destino', 'creado_por')


@admin.register(CDP)
class CDPAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero', 'apropiacion', 'valor', 'saldo_disponible', 'estado', 'vigencia', 'institucion')
    list_filter = ('estado', 'vigencia')
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'vigencia', 'apropiacion', 'creado_por')

    @admin.display(description='Saldo disponible')
    def saldo_disponible(self, obj):
        return f"${obj.saldo_disponible:,.2f}"


@admin.register(RP)
class RPAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero', 'cdp', 'tercero', 'categoria_cpc', 'valor', 'saldo_disponible', 'estado', 'institucion')
    list_filter = ('estado',)
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'cdp', 'tercero', 'categoria_cpc', 'creado_por')

    @admin.display(description='Saldo disponible')
    def saldo_disponible(self, obj):
        return f"${obj.saldo_disponible:,.2f}"


@admin.register(Obligacion)
class ObligacionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero', 'rp', 'valor', 'saldo_disponible', 'estado', 'institucion')
    list_filter = ('estado',)
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'rp', 'creado_por')

    @admin.display(description='Saldo disponible')
    def saldo_disponible(self, obj):
        return f"${obj.saldo_disponible:,.2f}"


@admin.register(OrdenDePago)
class OrdenDePagoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero', 'obligacion', 'beneficiario', 'valor_bruto', 'total_retenciones', 'valor_neto', 'estado', 'institucion')
    list_filter = ('estado',)
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'obligacion', 'beneficiario', 'creado_por')


@admin.register(CatalogoGeneralCuentas)
class CatalogoGeneralCuentasAdmin(admin.ModelAdmin):
    """Catálogo GLOBAL de plataforma (sin institución) — mismo criterio que
    DBAPredefinido en piar/simulacros: es un catálogo de referencia, no un
    dato de un colegio. Lo administra el propietario de la plataforma."""
    list_display = ('codigo', 'nombre', 'naturaleza', 'cuenta_padre', 'permite_movimientos', 'activo')
    list_filter = ('naturaleza', 'permite_movimientos', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    raw_id_fields = ('cuenta_padre',)


@admin.register(FuenteFinanciacion)
class FuenteFinanciacionAdmin(admin.ModelAdmin):
    """Catálogo GLOBAL de plataforma (sin institución) — Fuentes de
    Financiación oficiales del CHIP (Contaduría General de la Nación),
    mismo criterio que CatalogoGeneralCuentasAdmin."""
    list_display = ('codigo_fuente', 'nombre_cuenta', 'aplica_establecimientos_publicos_territoriales')
    list_filter = ('aplica_establecimientos_publicos_territoriales',)
    search_fields = ('codigo_fuente', 'nombre_cuenta')
    ordering = ('codigo_fuente',)


@admin.register(CategoriaCPC)
class CategoriaCPCAdmin(admin.ModelAdmin):
    """Catálogo GLOBAL de plataforma (sin institución) — Clasificación
    Central de Productos del DANE, mismo criterio que
    CatalogoGeneralCuentasAdmin. ~9.933 filas: sin list_filter por tipo
    para no listar miles de enlaces en el sidebar del admin (search_fields
    ya cubre la búsqueda por código o título)."""
    list_display = ('codigo', 'titulo', 'tipo')
    search_fields = ('codigo', 'titulo')
    ordering = ('codigo',)


@admin.register(ConceptoRetencion)
class ConceptoRetencionAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'tarifa_porcentaje', 'cuenta_puc_pasivo', 'institucion', 'activo')
    list_filter = ('tipo', 'activo')
    raw_id_fields = ('institucion', 'cuenta_puc_pasivo')


class MovimientoContableInline(admin.TabularInline):
    model = MovimientoContable
    extra = 0
    raw_id_fields = ('cuenta', 'tercero')


@admin.register(ComprobanteContable)
class ComprobanteContableAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'estado', 'orden_pago', 'vigencia', 'fecha', 'institucion')
    list_filter = ('tipo', 'estado', 'vigencia')
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'vigencia', 'orden_pago', 'comprobante_que_reversa', 'cuenta_bancaria', 'contabilizado_por')
    inlines = [MovimientoContableInline]


@admin.register(RetencionAplicada)
class RetencionAplicadaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    institucion_lookup = 'orden_pago__institucion'
    list_display = ('orden_pago', 'concepto', 'base_gravable', 'tarifa_porcentaje', 'valor')
    raw_id_fields = ('orden_pago', 'concepto')


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('banco', 'numero_cuenta', 'tipo', 'cuenta_cgc', 'saldo_actual', 'institucion', 'activa')
    list_filter = ('tipo', 'activa')
    raw_id_fields = ('institucion', 'cuenta_cgc')

    @admin.display(description='Saldo actual')
    def saldo_actual(self, obj):
        return f"${obj.saldo_actual:,.2f}"


@admin.register(MovimientoTesoreria)
class MovimientoTesoreriaAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('cuenta_bancaria', 'tipo', 'valor', 'concepto', 'fecha', 'conciliado', 'institucion')
    list_filter = ('tipo', 'conciliado')
    ordering = ('-fecha',)
    raw_id_fields = ('institucion', 'cuenta_bancaria', 'comprobante_contable')


@admin.register(ElementoAlmacen)
class ElementoAlmacenAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'unidad_medida', 'stock_actual', 'stock_minimo', 'institucion', 'activo')
    search_fields = ('codigo', 'nombre')
    raw_id_fields = ('institucion',)

    @admin.display(description='Stock actual')
    def stock_actual(self, obj):
        return obj.stock_actual


@admin.register(MovimientoAlmacen)
class MovimientoAlmacenAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('elemento', 'tipo', 'cantidad', 'valor_total', 'rp', 'responsable', 'fecha', 'institucion')
    list_filter = ('tipo',)
    ordering = ('-fecha',)
    raw_id_fields = ('institucion', 'elemento', 'rp', 'creado_por')
