from django.contrib import admin

from proyecto_colegio.admin_mixins import InstitucionScopedAdminMixin

from .models import (
    CDP,
    RP,
    Apropiacion,
    ModificacionPresupuestal,
    Obligacion,
    OrdenDePago,
    PresupuestoIngreso,
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
    list_filter = ('tipo_recurso', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    raw_id_fields = ('institucion', 'rubro_padre')


@admin.register(RubroPresupuestalGasto)
class RubroPresupuestalGastoAdmin(InstitucionScopedAdminMixin, admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'tipo', 'institucion', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('codigo', 'nombre')
    ordering = ('codigo',)
    raw_id_fields = ('institucion', 'rubro_padre')


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
    list_display = ('numero', 'cdp', 'tercero', 'valor', 'saldo_disponible', 'estado', 'institucion')
    list_filter = ('estado',)
    ordering = ('-numero',)
    raw_id_fields = ('institucion', 'cdp', 'tercero', 'creado_por')

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
