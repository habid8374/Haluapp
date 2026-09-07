"""Vistas del módulo Presupuesto FSE (Fase 1 — Núcleo Presupuestal)."""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services
from .forms import (
    ApropiacionForm,
    CDPForm,
    ConceptoRetencionForm,
    GenerarComprobanteForm,
    ModificacionPresupuestalForm,
    ObligacionForm,
    OrdenDePagoForm,
    PresupuestoIngresoForm,
    RetencionAplicadaForm,
    RPForm,
    RubroPresupuestalGastoForm,
    RubroPresupuestalIngresoForm,
    VigenciaFiscalForm,
)
from .models import (
    CDP,
    RP,
    Apropiacion,
    CatalogoGeneralCuentas,
    ComprobanteContable,
    ConceptoRetencion,
    ModificacionPresupuestal,
    Obligacion,
    OrdenDePago,
    PresupuestoIngreso,
    RetencionAplicada,
    RubroPresupuestalGasto,
    RubroPresupuestalIngreso,
    VigenciaFiscal,
)

logger = logging.getLogger(__name__)


def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


def _es_gestor_presupuesto(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('administrador', 'rector', 'tesoreria') or user.is_superuser


def _requiere_gestor(request):
    """Devuelve None si el usuario puede gestionar presupuesto, o un redirect si no."""
    if not _es_gestor_presupuesto(request.user):
        messages.error(request, 'No tienes permiso para acceder al módulo de Presupuesto.')
        return redirect('gestion_academica:inicio_academico')
    return None


def _filtro_institucion(request):
    """Igual criterio que el resto de la plataforma: superusuario ve todo
    (sin filtrar), el resto solo su propia institución."""
    if request.user.is_superuser:
        return {}
    return {'institucion': _get_institucion(request)}


# ─────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    filtro = _filtro_institucion(request)
    vigencia_id = request.GET.get('vigencia')
    vigencias = VigenciaFiscal.objects.filter(**filtro).order_by('-anio')
    vigencia_actual = None
    if vigencia_id:
        vigencia_actual = vigencias.filter(pk=vigencia_id).first()
    if not vigencia_actual:
        vigencia_actual = vigencias.filter(estado=VigenciaFiscal.Estado.ABIERTA).first() or vigencias.first()

    apropiaciones = []
    if vigencia_actual:
        apropiaciones = list(Apropiacion.objects.filter(vigencia=vigencia_actual).select_related('rubro'))

    total_apropiado = sum((a.valor_definitivo for a in apropiaciones), start=0)
    total_comprometido = sum((a.total_comprometido for a in apropiaciones), start=0)
    total_disponible = sum((a.saldo_disponible for a in apropiaciones), start=0)

    context = {
        'titulo_pagina': 'Presupuesto FSE',
        'vigencias': vigencias,
        'vigencia_actual': vigencia_actual,
        'apropiaciones': apropiaciones,
        'total_apropiado': total_apropiado,
        'total_comprometido': total_comprometido,
        'total_disponible': total_disponible,
    }
    return render(request, 'presupuesto/dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────
# Vigencias fiscales
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_vigencias(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    vigencias = VigenciaFiscal.objects.filter(**_filtro_institucion(request)).order_by('-anio')
    return render(request, 'presupuesto/vigencia_lista.html', {
        'titulo_pagina': 'Vigencias Fiscales', 'vigencias': vigencias,
    })


@login_required
def crear_vigencia(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = VigenciaFiscalForm(request.POST, institucion=institucion)
        if form.is_valid():
            vigencia = form.save(commit=False)
            vigencia.institucion = institucion
            try:
                vigencia.full_clean()
                vigencia.save()
                messages.success(request, 'Vigencia %(anio)s abierta correctamente.' % {'anio': vigencia.anio})
                return redirect('presupuesto:lista_vigencias')
            except ValidationError as e:
                for field, errs in getattr(e, 'message_dict', {'__all__': e.messages}).items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
    else:
        form = VigenciaFiscalForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Abrir Vigencia Fiscal', 'form': form,
        'icono': 'bi-calendar-range', 'volver_url': 'presupuesto:lista_vigencias',
    })


@login_required
@require_POST
def cerrar_vigencia(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    filtro = _filtro_institucion(request)
    vigencia = get_object_or_404(VigenciaFiscal, pk=pk, **filtro)
    services.cerrar_vigencia(vigencia=vigencia, usuario=request.user)
    messages.success(request, 'Vigencia %(anio)s cerrada. No se podrán comprometer más recursos en ella.' % {'anio': vigencia.anio})
    return redirect('presupuesto:lista_vigencias')


# ─────────────────────────────────────────────────────────────────────────
# Rubros (ingreso / gasto)
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_rubros_ingreso(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    rubros = RubroPresupuestalIngreso.objects.filter(**_filtro_institucion(request)).order_by('codigo')
    return render(request, 'presupuesto/rubro_ingreso_lista.html', {
        'titulo_pagina': 'Rubros de Ingreso', 'rubros': rubros,
    })


@login_required
def crear_rubro_ingreso(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = RubroPresupuestalIngresoForm(request.POST, institucion=institucion)
        if form.is_valid():
            rubro = form.save(commit=False)
            rubro.institucion = institucion
            rubro.save()
            messages.success(request, 'Rubro de ingreso creado.')
            return redirect('presupuesto:lista_rubros_ingreso')
    else:
        form = RubroPresupuestalIngresoForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nuevo Rubro de Ingreso', 'form': form,
        'icono': 'bi-arrow-down-circle', 'volver_url': 'presupuesto:lista_rubros_ingreso',
    })


@login_required
def lista_rubros_gasto(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    rubros = RubroPresupuestalGasto.objects.filter(**_filtro_institucion(request)).order_by('codigo')
    return render(request, 'presupuesto/rubro_gasto_lista.html', {
        'titulo_pagina': 'Rubros de Gasto', 'rubros': rubros,
    })


@login_required
def crear_rubro_gasto(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = RubroPresupuestalGastoForm(request.POST, institucion=institucion)
        if form.is_valid():
            rubro = form.save(commit=False)
            rubro.institucion = institucion
            rubro.save()
            messages.success(request, 'Rubro de gasto creado.')
            return redirect('presupuesto:lista_rubros_gasto')
    else:
        form = RubroPresupuestalGastoForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nuevo Rubro de Gasto', 'form': form,
        'icono': 'bi-arrow-up-circle', 'volver_url': 'presupuesto:lista_rubros_gasto',
    })


# ─────────────────────────────────────────────────────────────────────────
# Presupuesto de ingresos
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_presupuesto_ingreso(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    items = PresupuestoIngreso.objects.filter(**_filtro_institucion(request)).select_related('rubro', 'vigencia').order_by('-vigencia__anio')
    return render(request, 'presupuesto/presupuesto_ingreso_lista.html', {
        'titulo_pagina': 'Presupuesto de Ingresos', 'items': items,
    })


@login_required
def crear_presupuesto_ingreso(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = PresupuestoIngresoForm(request.POST, institucion=institucion)
        if form.is_valid():
            item = form.save(commit=False)
            item.institucion = institucion
            try:
                item.full_clean()
                item.save()
                messages.success(request, 'Presupuesto de ingreso registrado.')
                return redirect('presupuesto:lista_presupuesto_ingreso')
            except ValidationError as e:
                for field, errs in getattr(e, 'message_dict', {'__all__': e.messages}).items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
    else:
        form = PresupuestoIngresoForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Registrar Presupuesto de Ingreso', 'form': form,
        'icono': 'bi-cash-coin', 'volver_url': 'presupuesto:lista_presupuesto_ingreso',
    })


# ─────────────────────────────────────────────────────────────────────────
# Apropiaciones y modificaciones
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_apropiaciones(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    apropiaciones = Apropiacion.objects.filter(**_filtro_institucion(request)).select_related('rubro', 'vigencia').order_by('-vigencia__anio', 'rubro__codigo')
    return render(request, 'presupuesto/apropiacion_lista.html', {
        'titulo_pagina': 'Apropiaciones Presupuestales', 'apropiaciones': apropiaciones,
    })


@login_required
def crear_apropiacion(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = ApropiacionForm(request.POST, institucion=institucion)
        if form.is_valid():
            apropiacion = form.save(commit=False)
            apropiacion.institucion = institucion
            try:
                apropiacion.full_clean()
                apropiacion.save()
                messages.success(request, 'Apropiación registrada.')
                return redirect('presupuesto:lista_apropiaciones')
            except ValidationError as e:
                for field, errs in getattr(e, 'message_dict', {'__all__': e.messages}).items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
    else:
        form = ApropiacionForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nueva Apropiación', 'form': form,
        'icono': 'bi-piggy-bank', 'volver_url': 'presupuesto:lista_apropiaciones',
    })


@login_required
def lista_modificaciones(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    mods = ModificacionPresupuestal.objects.filter(**_filtro_institucion(request)).select_related('apropiacion', 'apropiacion_destino').order_by('-fecha')
    return render(request, 'presupuesto/modificacion_lista.html', {
        'titulo_pagina': 'Modificaciones Presupuestales', 'modificaciones': mods,
    })


@login_required
def crear_modificacion(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = ModificacionPresupuestalForm(request.POST, request.FILES, institucion=institucion)
        if form.is_valid():
            mod = form.save(commit=False)
            mod.institucion = institucion
            mod.creado_por = request.user
            try:
                mod.full_clean()
                mod.save()
                messages.success(request, 'Modificación presupuestal registrada.')
                return redirect('presupuesto:lista_modificaciones')
            except ValidationError as e:
                for field, errs in getattr(e, 'message_dict', {'__all__': e.messages}).items():
                    for err in errs:
                        form.add_error(field if field != '__all__' else None, err)
    else:
        form = ModificacionPresupuestalForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nueva Modificación Presupuestal', 'form': form,
        'icono': 'bi-arrow-left-right', 'volver_url': 'presupuesto:lista_modificaciones',
    })


# ─────────────────────────────────────────────────────────────────────────
# CDP
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_cdp(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    cdps = CDP.objects.filter(**_filtro_institucion(request)).select_related('apropiacion', 'vigencia').order_by('-numero')
    return render(request, 'presupuesto/cdp_lista.html', {'titulo_pagina': 'Certificados de Disponibilidad (CDP)', 'cdps': cdps})


@login_required
def crear_cdp(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = CDPForm(request.POST, institucion=institucion)
        if form.is_valid():
            try:
                services.expedir_cdp(
                    apropiacion=form.cleaned_data['apropiacion'],
                    valor=form.cleaned_data['valor'],
                    objeto=form.cleaned_data['objeto'],
                    usuario=request.user,
                )
                messages.success(request, 'CDP expedido correctamente.')
                return redirect('presupuesto:lista_cdp')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = CDPForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Expedir CDP', 'form': form,
        'icono': 'bi-file-earmark-lock', 'volver_url': 'presupuesto:lista_cdp',
    })


@login_required
@require_POST
def anular_cdp(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    cdp = get_object_or_404(CDP, pk=pk, **_filtro_institucion(request))
    if cdp.total_comprometido_rp > 0:
        messages.error(request, 'No se puede anular: ya tiene Registros Presupuestales (RP) asociados.')
    else:
        cdp.estado = CDP.Estado.ANULADO
        cdp.anulado_motivo = request.POST.get('motivo', '')
        cdp.save(update_fields=['estado', 'anulado_motivo'])
        messages.success(request, 'CDP #%(num)s anulado.' % {'num': cdp.numero})
    return redirect('presupuesto:lista_cdp')


# ─────────────────────────────────────────────────────────────────────────
# RP
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_rp(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    rps = RP.objects.filter(**_filtro_institucion(request)).select_related('cdp', 'tercero').order_by('-numero')
    return render(request, 'presupuesto/rp_lista.html', {'titulo_pagina': 'Registros Presupuestales (RP)', 'rps': rps})


@login_required
def crear_rp(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = RPForm(request.POST, institucion=institucion)
        if form.is_valid():
            try:
                services.crear_rp(
                    cdp=form.cleaned_data['cdp'],
                    tercero=form.cleaned_data['tercero'],
                    objeto_contrato=form.cleaned_data['objeto_contrato'],
                    valor=form.cleaned_data['valor'],
                    usuario=request.user,
                )
                messages.success(request, 'Registro Presupuestal (RP) creado correctamente.')
                return redirect('presupuesto:lista_rp')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = RPForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nuevo Registro Presupuestal (RP)', 'form': form,
        'icono': 'bi-file-earmark-text', 'volver_url': 'presupuesto:lista_rp',
    })


@login_required
@require_POST
def anular_rp(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    rp = get_object_or_404(RP, pk=pk, **_filtro_institucion(request))
    if rp.total_obligado > 0:
        messages.error(request, 'No se puede anular: ya tiene Obligaciones asociadas.')
    else:
        rp.estado = RP.Estado.ANULADO
        rp.anulado_motivo = request.POST.get('motivo', '')
        rp.save(update_fields=['estado', 'anulado_motivo'])
        if rp.cdp.estado == CDP.Estado.AGOTADO:
            rp.cdp.estado = CDP.Estado.VIGENTE
            rp.cdp.save(update_fields=['estado'])
        messages.success(request, 'RP #%(num)s anulado.' % {'num': rp.numero})
    return redirect('presupuesto:lista_rp')


# ─────────────────────────────────────────────────────────────────────────
# Obligaciones
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_obligaciones(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    obligaciones = Obligacion.objects.filter(**_filtro_institucion(request)).select_related('rp', 'rp__tercero').order_by('-numero')
    return render(request, 'presupuesto/obligacion_lista.html', {'titulo_pagina': 'Obligaciones', 'obligaciones': obligaciones})


@login_required
def crear_obligacion(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = ObligacionForm(request.POST, request.FILES, institucion=institucion)
        if form.is_valid():
            try:
                services.causar_obligacion(
                    rp=form.cleaned_data['rp'],
                    valor=form.cleaned_data['valor'],
                    soporte=form.cleaned_data.get('soporte_recibido_satisfaccion'),
                    usuario=request.user,
                )
                messages.success(request, 'Obligación causada correctamente.')
                return redirect('presupuesto:lista_obligaciones')
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = ObligacionForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Causar Obligación', 'form': form,
        'icono': 'bi-file-earmark-check', 'volver_url': 'presupuesto:lista_obligaciones',
    })


@login_required
@require_POST
def anular_obligacion(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    obligacion = get_object_or_404(Obligacion, pk=pk, **_filtro_institucion(request))
    if obligacion.total_pagado > 0:
        messages.error(request, 'No se puede anular: ya tiene Órdenes de Pago asociadas.')
    else:
        obligacion.estado = Obligacion.Estado.ANULADA
        obligacion.anulado_motivo = request.POST.get('motivo', '')
        obligacion.save(update_fields=['estado', 'anulado_motivo'])
        if obligacion.rp.estado == RP.Estado.LIQUIDADO:
            obligacion.rp.estado = RP.Estado.VIGENTE
            obligacion.rp.save(update_fields=['estado'])
        messages.success(request, 'Obligación #%(num)s anulada.' % {'num': obligacion.numero})
    return redirect('presupuesto:lista_obligaciones')


# ─────────────────────────────────────────────────────────────────────────
# Órdenes de Pago
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_ordenes_pago(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    ordenes = OrdenDePago.objects.filter(**_filtro_institucion(request)).select_related('obligacion', 'beneficiario', 'comprobante_contable').order_by('-numero')
    return render(request, 'presupuesto/orden_pago_lista.html', {'titulo_pagina': 'Órdenes de Pago', 'ordenes': ordenes})


@login_required
def crear_orden_pago(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = OrdenDePagoForm(request.POST, institucion=institucion)
        if form.is_valid():
            try:
                orden = services.generar_orden_pago(
                    obligacion=form.cleaned_data['obligacion'],
                    usuario=request.user,
                )
                messages.success(request, 'Orden de Pago generada. Ahora puedes agregar retenciones si aplican y generar el comprobante contable.')
                return redirect('presupuesto:detalle_orden_pago', pk=orden.pk)
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = OrdenDePagoForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Generar Orden de Pago', 'form': form,
        'icono': 'bi-cash-stack', 'volver_url': 'presupuesto:lista_ordenes_pago',
    })


@login_required
def detalle_orden_pago(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    orden = get_object_or_404(
        OrdenDePago.objects.select_related('obligacion', 'beneficiario', 'comprobante_contable'),
        pk=pk, **_filtro_institucion(request),
    )
    institucion = _get_institucion(request) if not request.user.is_superuser else orden.institucion
    retenciones = orden.retenciones.select_related('concepto')
    form_retencion = RetencionAplicadaForm(institucion=institucion)
    tiene_comprobante = hasattr(orden, 'comprobante_contable')
    return render(request, 'presupuesto/orden_pago_detalle.html', {
        'titulo_pagina': f'Orden de Pago #{orden.numero}', 'orden': orden,
        'retenciones': retenciones, 'form_retencion': form_retencion,
        'tiene_comprobante': tiene_comprobante,
    })


@login_required
@require_POST
def agregar_retencion(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    orden = get_object_or_404(OrdenDePago, pk=pk, **_filtro_institucion(request))
    institucion = _get_institucion(request) if not request.user.is_superuser else orden.institucion
    form = RetencionAplicadaForm(request.POST, institucion=institucion)
    if form.is_valid():
        try:
            services.agregar_retencion(
                orden_pago=orden, concepto=form.cleaned_data['concepto'],
                base_gravable=form.cleaned_data['base_gravable'], usuario=request.user,
            )
            messages.success(request, 'Retención agregada.')
        except ValidationError as e:
            messages.error(request, e.message if hasattr(e, 'message') else str(e))
    else:
        messages.error(request, 'Datos inválidos para la retención.')
    return redirect('presupuesto:detalle_orden_pago', pk=pk)


@login_required
@require_POST
def quitar_retencion(request, pk, retencion_pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    orden = get_object_or_404(OrdenDePago, pk=pk, **_filtro_institucion(request))
    retencion = get_object_or_404(RetencionAplicada, pk=retencion_pk, orden_pago=orden)
    try:
        services.quitar_retencion(retencion=retencion, usuario=request.user)
        messages.success(request, 'Retención eliminada.')
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('presupuesto:detalle_orden_pago', pk=pk)


@login_required
def generar_comprobante(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    orden = get_object_or_404(OrdenDePago, pk=pk, **_filtro_institucion(request))
    if request.method == 'POST':
        form = GenerarComprobanteForm(request.POST)
        if form.is_valid():
            try:
                comprobante = services.generar_comprobante_contable(
                    orden_pago=orden, cuenta_bancos=form.cleaned_data['cuenta_bancos'], usuario=request.user,
                )
                messages.success(request, 'Comprobante contable generado en Borrador. Revísalo y contabilízalo.')
                return redirect('presupuesto:detalle_comprobante', pk=comprobante.pk)
            except ValidationError as e:
                form.add_error(None, e.message if hasattr(e, 'message') else str(e))
    else:
        form = GenerarComprobanteForm()
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': f'Generar Comprobante — Orden de Pago #{orden.numero}', 'form': form,
        'icono': 'bi-journal-text', 'volver_href': reverse('presupuesto:detalle_orden_pago', args=[orden.pk]),
    })


@login_required
@require_POST
def anular_orden_pago(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    orden = get_object_or_404(OrdenDePago, pk=pk, **_filtro_institucion(request))
    if hasattr(orden, 'comprobante_contable'):
        messages.error(request, 'No se puede anular: ya tiene un comprobante contable. Usa la opción de reversar el comprobante en su lugar.')
        return redirect('presupuesto:lista_ordenes_pago')
    orden.estado = OrdenDePago.Estado.ANULADA
    orden.anulado_motivo = request.POST.get('motivo', '')
    orden.save(update_fields=['estado', 'anulado_motivo'])
    if orden.obligacion.estado == Obligacion.Estado.PAGADA:
        orden.obligacion.estado = Obligacion.Estado.VIGENTE
        orden.obligacion.save(update_fields=['estado'])
    messages.success(request, 'Orden de Pago #%(num)s anulada.' % {'num': orden.numero})
    return redirect('presupuesto:lista_ordenes_pago')


# ─────────────────────────────────────────────────────────────────────────
# Conceptos de Retención
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_conceptos_retencion(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    conceptos = ConceptoRetencion.objects.filter(**_filtro_institucion(request)).select_related('cuenta_puc_pasivo')
    return render(request, 'presupuesto/concepto_retencion_lista.html', {
        'titulo_pagina': 'Conceptos de Retención', 'conceptos': conceptos,
    })


@login_required
def crear_concepto_retencion(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    institucion = _get_institucion(request)
    if request.method == 'POST':
        form = ConceptoRetencionForm(request.POST, institucion=institucion)
        if form.is_valid():
            concepto = form.save(commit=False)
            concepto.institucion = institucion
            concepto.save()
            messages.success(request, 'Concepto de retención creado.')
            return redirect('presupuesto:lista_conceptos_retencion')
    else:
        form = ConceptoRetencionForm(institucion=institucion)
    return render(request, 'presupuesto/form_generico.html', {
        'titulo_pagina': 'Nuevo Concepto de Retención', 'form': form,
        'icono': 'bi-percent', 'volver_url': 'presupuesto:lista_conceptos_retencion',
    })


# ─────────────────────────────────────────────────────────────────────────
# Comprobantes Contables
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_comprobantes(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    comprobantes = ComprobanteContable.objects.filter(**_filtro_institucion(request)).select_related('orden_pago', 'vigencia').order_by('-numero')
    return render(request, 'presupuesto/comprobante_lista.html', {
        'titulo_pagina': 'Comprobantes Contables', 'comprobantes': comprobantes,
    })


@login_required
def detalle_comprobante(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    comprobante = get_object_or_404(
        ComprobanteContable.objects.select_related('orden_pago', 'comprobante_que_reversa'),
        pk=pk, **_filtro_institucion(request),
    )
    movimientos = comprobante.movimientos.select_related('cuenta', 'tercero')
    return render(request, 'presupuesto/comprobante_detalle.html', {
        'titulo_pagina': f'Comprobante #{comprobante.numero}', 'comprobante': comprobante, 'movimientos': movimientos,
    })


@login_required
@require_POST
def contabilizar_comprobante(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    comprobante = get_object_or_404(ComprobanteContable, pk=pk, **_filtro_institucion(request))
    try:
        services.contabilizar_comprobante(comprobante=comprobante, usuario=request.user)
        messages.success(request, 'Comprobante contabilizado. Ya no se puede editar — a partir de ahora solo se reversa con un ajuste.')
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
    return redirect('presupuesto:detalle_comprobante', pk=pk)


@login_required
@require_POST
def reversar_comprobante(request, pk):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    comprobante = get_object_or_404(ComprobanteContable, pk=pk, **_filtro_institucion(request))
    motivo = request.POST.get('motivo', '')
    try:
        reverso = services.reversar_comprobante(comprobante=comprobante, usuario=request.user, motivo=motivo)
        messages.success(request, f'Comprobante reversado con el ajuste #{reverso.numero}.')
        return redirect('presupuesto:detalle_comprobante', pk=reverso.pk)
    except ValidationError as e:
        messages.error(request, e.message if hasattr(e, 'message') else str(e))
        return redirect('presupuesto:detalle_comprobante', pk=pk)


# ─────────────────────────────────────────────────────────────────────────
# Catálogo General de Cuentas (solo lectura — lo administra el propietario)
# ─────────────────────────────────────────────────────────────────────────

@login_required
def lista_catalogo_cgc(request):
    guard = _requiere_gestor(request)
    if guard:
        return guard
    cuentas = CatalogoGeneralCuentas.objects.filter(activo=True).select_related('cuenta_padre')
    return render(request, 'presupuesto/catalogo_cgc_lista.html', {
        'titulo_pagina': 'Catálogo General de Cuentas (CGC)', 'cuentas': cuentas,
    })
