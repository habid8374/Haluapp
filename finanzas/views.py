# finanzas/views.py
from io import BytesIO
import os
import json
import logging
from weasyprint import HTML
import urllib.parse
from decimal import Decimal
import calendar
from datetime import datetime, date, timedelta
from django.core.mail import EmailMessage
from xhtml2pdf import pisa
from django.conf import settings
from django.db import transaction, models
from django.db.models import Sum, F, Case, When, DecimalField, Count, Q, Value, CharField
from django.db.models.functions import Coalesce
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.core.management import call_command
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.template.loader import get_template
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
import io
import re
import mercadopago
from django.views.decorators.http import require_POST
from urllib.parse import urlencode
from django.core.mail import get_connection

from admisiones.utils import enviar_correo_dinamico
from django.template.loader import render_to_string

from collections import defaultdict

from .models import (
    InstitucionEducativa,
    TipoConceptoPago,
    ConceptoPago,
    CuentaPorCobrarEstudiante,
    PagoRegistrado,
    ESTADOS_CUENTA,
    NOMBRES_MESES_ESPANOL,
    CategoriaGasto,
    Proveedor,
    Gasto,
    Descuento,
    TipoGasto,
    CuentaContable,
    AuditoriaExportacionContable,
    ConsecutivoDocumento,
)

from gestion_academica.models import TicketSoporte, RespuestaTicket
from gestion_academica.forms import RespuestaTicketForm

from utils.mercadopago_webhook import resolve_notification_data_id, verify_mercadopago_webhook_signature
from finanzas.institucion_credentials import mp_webhook_secret as institucion_mp_webhook_secret

from .logic import aplicar_descuentos_a_cuenta

from gestion_academica.models import (
    Estudiante, 
    PeriodoAcademico, 
    Grado  # <-- IMPORTACIÓN AÑADIDA
)

from .forms import (
    ConfiguracionPagoForm, 
    TipoConceptoPagoForm, 
    ConceptoPagoForm, 
    CuentaPorCobrarEstudianteForm, 
    PagoForm,
    CategoriaGastoForm, 
    ProveedorForm, 
    GastoForm,
    DescuentoForm,
    FacturacionMasivaForm,
    ExportacionContableForm,
    LibroDiarioContableForm,
    TipoGastoForm, # <-- AÑADE ESTA IMPORTACIÓN
    CategoriaGastoForm,
    CuentaContableForm,
)

# Mixin para asegurar que todo sea multi-institución
class CuentaContableInstitucionMixin:
    def get_queryset(self):
        return CuentaContable.objects.filter(institucion=self.request.user.institucion_asociada)

from .mixins import InstitucionOwnedMixin, solo_institucion_privada

logger = logging.getLogger(__name__)


def _puede_acceder_dashboard_finanzas(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm("finanzas.acceso_modulo_finanzas"):
        return True
    return (
        user.has_perm("finanzas.view_pagoregistrado")
        or user.has_perm("finanzas.view_gasto")
        or user.has_perm("finanzas.view_cuentaporcobrarestudiante")
    )


def _puede_exportacion_contable(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if user.has_perm("finanzas.acceso_modulo_finanzas"):
        return True
    return user.has_perm("finanzas.view_pagoregistrado") or user.has_perm("finanzas.view_gasto")


def _periodo_desde_request(request, institucion):
    raw = request.GET.get("periodo") or request.POST.get("periodo")
    if not raw:
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    qs = PeriodoAcademico.objects.filter(pk=pk)
    if institucion:
        qs = qs.filter(institucion=institucion)
    return qs.first()


def _periodos_para_filtros(request):
    if request.user.is_superuser:
        return PeriodoAcademico.objects.order_by("-año_escolar", "-fecha_inicio")
    inst = getattr(request.user, "institucion_asociada", None)
    if not inst:
        return PeriodoAcademico.objects.none()
    return PeriodoAcademico.objects.filter(institucion=inst).order_by(
        "-año_escolar", "-fecha_inicio"
    )


def _filtrar_pagos_por_periodo(qs, periodo):
    if not periodo:
        return qs
    return qs.filter(fecha_pago__range=[periodo.fecha_inicio, periodo.fecha_fin])


def _movimientos_contables_rango(
    institucion, fecha_inicio, fecha_fin, tipo_transaccion, periodo_sel
):
    """
    Lista de movimientos (misma estructura que exportación contable), ordenada por fecha.
    """
    movimientos = []

    if tipo_transaccion in ("TODOS", "INGRESOS"):
        ingresos = PagoRegistrado.objects.filter(
            institucion=institucion,
            fecha_pago__range=[fecha_inicio, fecha_fin],
        ).select_related(
            "estudiante__usuario",
            "cuenta__concepto_pago__cuenta_contable",
        )
        ingresos = _filtrar_pagos_por_periodo(ingresos, periodo_sel)

        for pago in ingresos:
            cc = pago.cuenta.concepto_pago.cuenta_contable
            movimientos.append(
                {
                    "ID interno": pago.pk,
                    "Fecha": pago.fecha_pago,
                    "Tipo": "Ingreso",
                    "Código PUC": cc.codigo if cc else "",
                    "Nombre cuenta PUC": cc.nombre if cc else "",
                    "Documento tercero": pago.estudiante.documento_identidad or "",
                    "Nombre tercero": pago.estudiante.usuario.get_full_name()
                    or pago.estudiante.usuario.username,
                    "Concepto": pago.cuenta.concepto_pago.nombre_concepto,
                    "Método de pago": pago.get_metodo_pago_display(),
                    "Referencia transacción": (pago.referencia_transaccion or "").strip(),
                    "N° recibo / documento": pago.numero_documento or "",
                    "Observación": (pago.observacion or "")[:500],
                    "Débito": Decimal("0.00"),
                    "Crédito": pago.valor_pagado,
                }
            )

    if tipo_transaccion in ("TODOS", "GASTOS"):
        gastos = Gasto.objects.filter(
            institucion=institucion,
            fecha_gasto__range=[fecha_inicio, fecha_fin],
        ).select_related("proveedor", "categoria__cuenta_contable")

        for gasto in gastos:
            cc = gasto.categoria.cuenta_contable
            movimientos.append(
                {
                    "ID interno": gasto.pk,
                    "Fecha": gasto.fecha_gasto,
                    "Tipo": "Gasto",
                    "Código PUC": cc.codigo if cc else "",
                    "Nombre cuenta PUC": cc.nombre if cc else "",
                    "Documento tercero": gasto.proveedor.nit_o_cedula
                    if gasto.proveedor
                    else "",
                    "Nombre tercero": gasto.proveedor.nombre
                    if gasto.proveedor
                    else "Varios",
                    "Concepto": gasto.descripcion,
                    "Método de pago": "",
                    "Referencia transacción": "",
                    "N° recibo / documento": gasto.numero_documento or "",
                    "Observación": "",
                    "Débito": gasto.monto,
                    "Crédito": Decimal("0.00"),
                }
            )

    movimientos.sort(key=lambda x: x["Fecha"])
    return movimientos


def _movimiento_fila_libro_tabla(m):
    """Claves seguras para plantillas (evita espacios en nombres de campo)."""
    return {
        "fecha": m["Fecha"],
        "tipo": m["Tipo"],
        "codigo_puc": m["Código PUC"],
        "nombre_puc": m["Nombre cuenta PUC"],
        "documento_tercero": m["Documento tercero"],
        "nombre_tercero": m["Nombre tercero"],
        "concepto": m["Concepto"],
        "metodo_pago": m["Método de pago"],
        "referencia": m["Referencia transacción"],
        "numero_documento": m["N° recibo / documento"],
        "observacion": m["Observación"],
        "debito": m["Débito"],
        "credito": m["Crédito"],
        "id_interno": m["ID interno"],
    }


def _alertas_puc_institucion(institucion):
    if not institucion:
        return {"conceptos_sin_puc": 0, "categorias_sin_puc": 0}
    return {
        "conceptos_sin_puc": ConceptoPago.objects.filter(
            institucion=institucion, cuenta_contable__isnull=True
        ).count(),
        "categorias_sin_puc": CategoriaGasto.objects.filter(
            institucion=institucion, cuenta_contable__isnull=True
        ).count(),
    }


# --- VISTAS DE CONFIGURACIÓN Y DASHBOARD ---

@login_required
@permission_required('finanzas.change_institucioneducativa', raise_exception=True)
def configurar_pagos(request):
    try:
        institucion = request.user.institucion_asociada
    except AttributeError:
        messages.error(request, "Tu usuario no está asociado a ninguna institución.")
        return redirect('gestion_academica:inicio_academico')

    if request.method == 'POST':
        form = ConfiguracionPagoForm(request.POST, instance=institucion)
        if form.is_valid():
            form.save()
            messages.success(request, "La configuración de la pasarela de pagos ha sido actualizada.")
            return redirect('finanzas:configurar_pagos')
    else:
        form = ConfiguracionPagoForm(instance=institucion)

    # Consecutivo de recibos de EFECTIVO (próximo número a usar) y cuántos
    # pagos en efectivo ya existen (para advertir antes de reiniciar).
    consecutivo_efectivo = ConsecutivoDocumento.objects.filter(
        institucion=institucion, tipo_documento='recibo_efectivo'
    ).first()
    proximo_recibo = consecutivo_efectivo.siguiente_numero if consecutivo_efectivo else 1
    pagos_efectivo_count = PagoRegistrado.objects.filter(
        institucion=institucion, metodo_pago='EFECTIVO'
    ).count()

    context = {
        'form': form,
        'titulo_pagina': "Configuración de Pagos",
        'proximo_recibo': proximo_recibo,
        'pagos_efectivo_count': pagos_efectivo_count,
    }
    return render(request, 'finanzas/configuracion_pagos.html', context)


@login_required
@permission_required('finanzas.change_institucioneducativa', raise_exception=True)
@require_POST
def reiniciar_consecutivo_efectivo(request):
    """Reinicia el consecutivo de recibos de EFECTIVO de la institución.

    Permite indicar el número de inicio (por defecto 1). Útil al limpiar
    datos de prueba o al migrar desde una talonera física.
    Aislamiento multi-institución: solo afecta el consecutivo de la
    institución del usuario.
    """
    institucion = getattr(request.user, 'institucion_asociada', None)
    if not institucion and not request.user.is_superuser:
        messages.error(request, "Tu usuario no está asociado a ninguna institución.")
        return redirect('gestion_academica:inicio_academico')

    try:
        nuevo_inicio = int(request.POST.get('numero_inicio', 1))
    except (TypeError, ValueError):
        nuevo_inicio = 1
    if nuevo_inicio < 1:
        nuevo_inicio = 1

    consecutivo, _ = ConsecutivoDocumento.objects.get_or_create(
        institucion=institucion,
        tipo_documento='recibo_efectivo',
        defaults={'siguiente_numero': nuevo_inicio},
    )
    consecutivo.siguiente_numero = nuevo_inicio
    consecutivo.save(update_fields=['siguiente_numero'])

    messages.success(
        request,
        f"Consecutivo de recibos de efectivo reiniciado. El próximo recibo será el "
        f"#{nuevo_inicio:06d}."
    )
    return redirect('finanzas:configurar_pagos')


@login_required
@solo_institucion_privada
def dashboard_financiero(request):
    """
    KPIs por periodo (mes actual, mes anterior o año en curso) y resumen de cartera.
    """
    if not _puede_acceder_dashboard_finanzas(request.user):
        messages.error(request, "No tiene permisos para acceder al panel de finanzas.")
        return redirect('gestion_academica:inicio_academico')
    periodo = request.GET.get('periodo', 'mes_actual')
    if periodo not in ('mes_actual', 'mes_anterior', 'anio'):
        periodo = 'mes_actual'

    today = timezone.now().date()
    if periodo == 'mes_anterior':
        primer_dia_este_mes = today.replace(day=1)
        ultimo_dia_mes_anterior = primer_dia_este_mes - timedelta(days=1)
        fecha_inicio = ultimo_dia_mes_anterior.replace(day=1)
        fecha_fin = ultimo_dia_mes_anterior
        etiqueta_periodo = f"{NOMBRES_MESES_ESPANOL[fecha_inicio.month]} {fecha_inicio.year}"
    elif periodo == 'anio':
        fecha_inicio = today.replace(month=1, day=1)
        fecha_fin = today
        etiqueta_periodo = f"Año {today.year} (acumulado a la fecha)"
    else:
        fecha_inicio = today.replace(day=1)
        fecha_fin = today
        etiqueta_periodo = f"{NOMBRES_MESES_ESPANOL[today.month]} {today.year} (mes en curso)"

    institucion_usuario = getattr(request.user, 'institucion_asociada', None)
    contexto_kpis = {}
    proximos_vencimientos = []

    if request.user.is_superuser:
        pagos_qs = PagoRegistrado.objects.all()
        gastos_qs = Gasto.objects.all()
        cuentas_qs = CuentaPorCobrarEstudiante.objects.all()
    elif institucion_usuario:
        pagos_qs = PagoRegistrado.objects.filter(institucion=institucion_usuario)
        gastos_qs = Gasto.objects.filter(institucion=institucion_usuario)
        cuentas_qs = CuentaPorCobrarEstudiante.objects.filter(institucion=institucion_usuario)
    else:
        pagos_qs = PagoRegistrado.objects.none()
        gastos_qs = Gasto.objects.none()
        cuentas_qs = CuentaPorCobrarEstudiante.objects.none()

    if request.user.is_superuser or institucion_usuario:
        ingresos_periodo = pagos_qs.filter(
            fecha_pago__range=[fecha_inicio, fecha_fin]
        ).aggregate(total=Sum('valor_pagado'))['total'] or Decimal('0.00')

        gastos_periodo = gastos_qs.filter(
            fecha_gasto__range=[fecha_inicio, fecha_fin]
        ).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

        ingresos_mp = pagos_qs.filter(
            fecha_pago__range=[fecha_inicio, fecha_fin],
            metodo_pago='MERCADO_PAGO',
        ).aggregate(total=Sum('valor_pagado'))['total'] or Decimal('0.00')
        ingresos_otros = ingresos_periodo - ingresos_mp

        saldo_annotation = dict(
            total_pagado=Coalesce(Sum('pagos__valor_pagado'), Decimal('0.00')),
        )
        cuentas_con_saldo = (
            cuentas_qs.exclude(estado='ANULADO')
            .annotate(**saldo_annotation)
            .annotate(saldo=F('monto_asignado') - F('total_pagado'))
            .filter(saldo__gt=0)
        )
        cartera_pendiente_total = cuentas_con_saldo.aggregate(t=Sum('saldo'))['t'] or Decimal('0.00')

        cuentas_mora = cuentas_con_saldo.filter(fecha_vencimiento_especifica__lt=today)
        cuentas_mora_count = cuentas_mora.count()
        cartera_mora_valor = cuentas_mora.aggregate(t=Sum('saldo'))['t'] or Decimal('0.00')

        proximos_vencimientos = list(
            cuentas_con_saldo.filter(fecha_vencimiento_especifica__gte=today)
            .select_related('estudiante__usuario', 'concepto_pago', 'aspirante')
            .order_by('fecha_vencimiento_especifica')[:8]
        )

        contexto_kpis = {
            'ingresos_periodo': ingresos_periodo,
            'gastos_periodo': gastos_periodo,
            'utilidad_periodo': ingresos_periodo - gastos_periodo,
            'cartera_pendiente_total': cartera_pendiente_total,
            'cartera_mora_valor': cartera_mora_valor,
            'cuentas_mora_count': cuentas_mora_count,
            'ingresos_mercadopago': ingresos_mp,
            'ingresos_otros_medios': ingresos_otros,
        }

    puede_cargar_puc = request.user.is_superuser or request.user.has_perm('finanzas.add_cuentacontable')
    puede_config_pagos = request.user.is_superuser or request.user.has_perm(
        'finanzas.change_institucioneducativa'
    )
    puede_exportacion_contable = _puede_exportacion_contable(request.user)
    alertas_puc = _alertas_puc_institucion(institucion_usuario)

    context = {
        'titulo_pagina': 'Dashboard Financiero',
        'kpis': contexto_kpis,
        'periodo_seleccionado': periodo,
        'etiqueta_periodo': etiqueta_periodo,
        'fecha_periodo_inicio': fecha_inicio,
        'fecha_periodo_fin': fecha_fin,
        'proximos_vencimientos': proximos_vencimientos,
        'puede_cargar_puc': puede_cargar_puc,
        'puede_config_pagos': puede_config_pagos,
        'puede_exportacion_contable': puede_exportacion_contable,
        'alertas_puc': alertas_puc,
    }
    return render(request, 'finanzas/dashboard_financiero.html', context)


@login_required
def reportes_exportaciones_hub(request):
    if not _puede_acceder_dashboard_finanzas(request.user):
        messages.error(request, "No tiene permisos para acceder al panel de finanzas.")
        return redirect('gestion_academica:inicio_academico')
    puede_export = _puede_exportacion_contable(request.user)
    inst = getattr(request.user, "institucion_asociada", None)
    periodo_activo = (
        PeriodoAcademico.objects.filter(institucion=inst, activo=True).first()
        if inst
        else None
    )
    auditorias = (
        AuditoriaExportacionContable.objects.filter(institucion=inst)
        .select_related("usuario", "periodo_academico")
        .order_by("-creado")[:12]
        if inst
        else []
    )
    return render(
        request,
        "finanzas/reportes_exportaciones.html",
        {
            "titulo_pagina": "Reportes y exportaciones",
            "puede_exportacion_contable": puede_export,
            "periodo_activo": periodo_activo,
            "periodos_filtro": _periodos_para_filtros(request),
            "alertas_puc": _alertas_puc_institucion(inst),
            "auditorias_exportacion": auditorias,
        },
    )


@login_required
def vista_financiera_dashboard(request):
    if not _puede_acceder_dashboard_finanzas(request.user):
        messages.error(request, "No tiene permisos para acceder al panel de finanzas.")
        return redirect('gestion_academica:inicio_academico')

    institucion = getattr(request.user, 'institucion_asociada', None)
    if request.user.is_superuser:
        base_qs = Estudiante.objects.all()
    elif institucion:
        base_qs = Estudiante.objects.filter(institucion=institucion)
    else:
        base_qs = Estudiante.objects.none()

    estudiantes_qs = (
        base_qs
        .select_related('usuario', 'grado_actual')
        .annotate(
            total_asignado=Coalesce(
                Sum('cuentas_por_cobrar__monto_asignado',
                    filter=~Q(cuentas_por_cobrar__estado='ANULADO')),
                Decimal('0.00'),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            num_vencido=Count('cuentas_por_cobrar',
                              filter=Q(cuentas_por_cobrar__estado='VENCIDO')),
            num_parcial=Count('cuentas_por_cobrar',
                              filter=Q(cuentas_por_cobrar__estado='PAGADO_PARCIAL')),
            num_pendiente=Count('cuentas_por_cobrar',
                                filter=Q(cuentas_por_cobrar__estado='PENDIENTE')),
            num_cuentas=Count('cuentas_por_cobrar',
                              filter=~Q(cuentas_por_cobrar__estado='ANULADO')),
        )
        .order_by('grado_actual__nombre', 'usuario__last_name', 'usuario__first_name')
    )

    # Clasificar estado financiero y agrupar por grado
    grados = {}  # {grado_key: {nombre, pk, estudiantes, contadores}}
    for est in estudiantes_qs:
        if est.num_vencido > 0:
            est.estado_financiero = 'MORA'
        elif est.num_parcial > 0:
            est.estado_financiero = 'PARCIAL'
        elif est.num_pendiente > 0:
            est.estado_financiero = 'PENDIENTE'
        else:
            est.estado_financiero = 'AL_DIA'

        grado_pk = est.grado_actual.pk if est.grado_actual else 0
        grado_nombre = est.grado_actual.nombre if est.grado_actual else 'Sin grado asignado'

        if grado_pk not in grados:
            grados[grado_pk] = {
                'nombre': grado_nombre,
                'estudiantes': [],
                'total': 0, 'en_mora': 0, 'parcial': 0,
                'pendiente': 0, 'al_dia': 0,
            }
        g = grados[grado_pk]
        g['estudiantes'].append(est)
        g['total'] += 1
        g['en_mora'] += est.estado_financiero == 'MORA'
        g['parcial'] += est.estado_financiero == 'PARCIAL'
        g['pendiente'] += est.estado_financiero == 'PENDIENTE'
        g['al_dia'] += est.estado_financiero == 'AL_DIA'

    # Ordenar grados: los nombrados primero (alfabético), "Sin grado" al final
    grados_lista = [grados[k] for k in sorted(grados, key=lambda k: (k == 0, grados[k]['nombre']))]

    return render(request, 'finanzas/listado_estudiantes.html', {
        'grados_lista': grados_lista,
        'titulo_pagina': 'Cartera por Estudiante',
    })


# --- CRUD PARA TIPO DE CONCEPTO DE PAGO ---

class TipoConceptoPagoListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = TipoConceptoPago
    template_name = 'finanzas/listado_configuracion.html' # <-- CORREGIDO
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_tipoconceptopago'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Tipos de Concepto de Pago"
        context["url_crear"] = reverse_lazy('finanzas:crear_tipo_concepto_pago')
        return context

class TipoConceptoPagoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TipoConceptoPago
    form_class = TipoConceptoPagoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_tipos_concepto_pago')
    permission_required = 'finanzas.add_tipoconceptopago'

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Tipo de concepto creado exitosamente.")
        return super().form_valid(form)

    # ▼▼▼ MÉTODO AÑADIDO PARA SOLUCIONAR EL ERROR ▼▼▼
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Nuevo Tipo de Concepto"
        # Añadimos la URL de cancelación como respaldo para el botón
        context["cancel_url"] = self.success_url 
        return context

class TipoConceptoPagoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = TipoConceptoPago
    form_class = TipoConceptoPagoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_tipos_concepto_pago')
    permission_required = 'finanzas.change_tipoconceptopago'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Tipo de Concepto"
        # ▼▼▼ LÍNEA AÑADIDA ▼▼▼
        context["cancel_url"] = self.success_url
        return context

class TipoConceptoPagoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = TipoConceptoPago
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_tipos_concepto_pago')
    permission_required = 'finanzas.delete_tipoconceptopago'

# --- CRUD PARA CUENTA POR COBRAR ---

class CuentaPorCobrarEstudianteListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = CuentaPorCobrarEstudiante
    template_name = 'finanzas/cuenta_por_cobrar_lista.html'
    context_object_name = 'cuentas_por_cobrar'
    permission_required = 'finanzas.view_cuentaporcobrarestudiante'

    def get_queryset(self):
        # Llama al queryset del mixin para la seguridad
        queryset = super().get_queryset()
        # Ordena por apellido de estudiante, luego por fecha, y optimiza la consulta
        return queryset.select_related(
            'estudiante__usuario', 
            'concepto_pago'
        ).order_by(
            'estudiante__usuario__last_name', 
            'estudiante__usuario__first_name', 
            '-fecha_vencimiento_especifica'
        )


# --- VISTAS DE ACCIONES Y REPORTES ---

@login_required
@permission_required('finanzas.add_pagoregistrado', raise_exception=True)
def registrar_pago(request, cuenta_id):
    if request.user.is_superuser:
        cuenta = get_object_or_404(CuentaPorCobrarEstudiante, id=cuenta_id)
    else:
        cuenta = get_object_or_404(CuentaPorCobrarEstudiante, id=cuenta_id, institucion=request.user.institucion_asociada)

    if request.method == 'POST':
        form = PagoForm(request.POST, cuenta=cuenta)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.cuenta = cuenta
            pago.estudiante = cuenta.estudiante
            pago.institucion = cuenta.institucion
            pago.registrado_por = request.user
            pago.save() # El signal post_save actualizará el estado de la cuenta a 'PAGADO'

            # Modo B (facturación electrónica automática): no-op salvo que la
            # institución tenga el módulo operativo + emisión automática activada.
            try:
                from facturacion_electronica.emision import disparar_emision_automatica
                disparar_emision_automatica(pago)
            except Exception:
                pass

            # --- INICIO DE LA LÓGICA DE SINCRONIZACIÓN CON ADMISIONES ---
            try:
                concepto_pagado = pago.cuenta.concepto_pago
                aspirante = pago.cuenta.aspirante or (pago.estudiante and pago.estudiante.aspirante_origen)

                # Si el pago es de matrícula y el aspirante está esperando ser matriculado
                if aspirante and concepto_pagado.es_pago_matricula and aspirante.estado == 'APROBADO_MATRICULA':
                    _, resultado_cuentas = aspirante.matricular()
                    messages.info(request, f"El estado del aspirante '{aspirante}' ha sido actualizado a 'Matriculado'.")
                    if resultado_cuentas.es_warning:
                        messages.warning(
                            request,
                            f"⚠ Pero NO se generaron todas las cuentas automáticas: "
                            f"{resultado_cuentas.mensaje}",
                        )
                
                # Si el pago es de inscripción y el aspirante está inscrito
                elif aspirante and concepto_pagado.es_pago_inscripcion and aspirante.estado == 'INSCRITO':
                    aspirante.estado = 'ADMITIDO'
                    aspirante.save(update_fields=['estado'])
                    messages.info(request, f"El estado del aspirante '{aspirante}' ha sido actualizado a 'Admitido'.")

            except Exception as e:
                logger.error(f"Error al intentar actualizar el estado del aspirante tras pago manual: {e}", exc_info=True)
                messages.warning(request, "El pago se registró, pero hubo un error al actualizar el estado del aspirante.")
            # --- FIN DE LA LÓGICA DE SINCRONIZACIÓN ---

            # --- INICIO DE LA LÓGICA DE ENVÍO DE CORREO CORREGIDA ---
            try:
                institucion = pago.institucion
                
                # 1. Creamos una conexión SMTP dinámica con las credenciales de la institución
                connection = get_connection(
                    host=institucion.email_host,
                    port=institucion.email_port,
                    username=institucion.email_host_user,
                    password=institucion.email_host_password,
                    use_tls=institucion.email_use_tls
                )

                # El resto de la lógica para generar el PDF se mantiene igual
                domain = f'{request.scheme}://{request.get_host()}'
                template_path = 'finanzas/emails/recibo_pago.html'
                template = get_template(template_path)
                context = {'pago': pago, 'institucion': institucion, 'domain': domain}
                html = template.render(context)
                
                pdf_buffer = BytesIO()
                pisa_status = pisa.CreatePDF(html, dest=pdf_buffer, link_callback=link_callback)
                if pisa_status.err:
                    raise Exception(f"Error al generar el PDF: {pisa_status.err}")
                pdf_buffer.seek(0)
                
                email_acudiente = getattr(pago.estudiante, 'email_acudiente', None)
                email_destinatario = email_acudiente or pago.estudiante.usuario.email
                
                if email_destinatario:
                    asunto = f"Recibo de Pago - {institucion.nombre}"
                    remitente = f'"{institucion.nombre}" <{institucion.email_host_user}>'
                    
                    # 2. Creamos el objeto EmailMessage y le pasamos la conexión que creamos
                    email = EmailMessage(
                        asunto,
                        html, # El cuerpo principal ahora es el HTML
                        remitente,
                        [email_destinatario],
                        connection=connection # <-- Usamos la conexión dinámica
                    )
                    email.content_subtype = "html"
                    email.attach(f'Recibo_Pago_{pago.id}.pdf', pdf_buffer.getvalue(), 'application/pdf')
                    email.send()
                    
                    messages.success(request, f"Pago de ${pago.valor_pagado} registrado y recibo enviado por correo.")
                else:
                    messages.warning(request, "Pago registrado, pero no se pudo notificar (sin email de destinatario).")

            except Exception as e:
                logger.error(f"Error al enviar correo de recibo: {e}", exc_info=True)
                messages.warning(request, f"Pago registrado, pero ocurrió un error al enviar la notificación: {e}")

            return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=cuenta.estudiante.pk)
    else:
        form = PagoForm(cuenta=cuenta)

    # Próximo número de recibo que se asignará SI el pago es en efectivo.
    consecutivo_efectivo = ConsecutivoDocumento.objects.filter(
        institucion=cuenta.institucion, tipo_documento='recibo_efectivo'
    ).first()
    proximo_recibo_efectivo = consecutivo_efectivo.siguiente_numero if consecutivo_efectivo else 1

    context = {
        'form': form,
        'cuenta': cuenta,
        'titulo_pagina': "Registrar Nuevo Pago",
        'proximo_recibo_efectivo': proximo_recibo_efectivo,
    }
    return render(request, 'finanzas/formulario_pago.html', context)

@login_required
@permission_required('finanzas.change_pagoregistrado', raise_exception=True)
def editar_pago(request, pago_id):
    pago = get_object_or_404(PagoRegistrado, id=pago_id) # La seguridad se debe añadir aquí
    
    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago, cuenta=pago.cuenta)
        if form.is_valid():
            form.save()
            
            # Lógica para enviar correo de notificación si el admin lo eligió
            if form.cleaned_data.get('notificar_cambios'):
                try:
                    # Generar el nuevo PDF
                    template = get_template('finanzas/emails/recibo_pago.html')
                    context = {'pago': pago, 'institucion': pago.institucion}
                    html = template.render(context)
                    pdf_buffer = BytesIO()
                    pisa.CreatePDF(html, dest=pdf_buffer)
                    pdf_buffer.seek(0)

                    # Preparar y enviar el correo
                    asunto = f"Corrección de Recibo de Pago - {pago.institucion.nombre}"
                    cuerpo_html = get_template('finanzas/emails/email_correccion_pago.html').render({'pago': pago, 'institucion': pago.institucion})
                    email_destinatario = pago.estudiante.email_acudiente or pago.estudiante.usuario.email
                    
                    if email_destinatario:
                        inst = pago.institucion
                        remitente = f'"{inst.nombre}" <{inst.email_host_user}>'
                        corr_conn = get_connection(
                            backend='django.core.mail.backends.smtp.EmailBackend',
                            host=inst.email_host, port=inst.email_port,
                            username=inst.email_host_user, password=inst.email_host_password,
                            use_tls=inst.email_use_tls,
                        )
                        email = EmailMessage(asunto, cuerpo_html, remitente, [email_destinatario], connection=corr_conn)
                        email.content_subtype = "html"
                        email.attach(f'Recibo_Corregido_{pago.id}.pdf', pdf_buffer.getvalue(), 'application/pdf')
                        email.send()
                        messages.success(request, "Pago actualizado y notificación enviada.")
                    else:
                        messages.warning(request, "Pago actualizado, pero no se pudo notificar (sin email).")
                
                except Exception as e:
                    logger.error(f"Error enviando correo de corrección: {e}")
                    messages.warning(request, "Pago actualizado, pero hubo un error al enviar la notificación.")
            else:
                messages.success(request, "Pago actualizado exitosamente.")
                
            return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=pago.estudiante.pk)
    else:
        form = PagoForm(instance=pago, cuenta=pago.cuenta)

    context = {'form': form, 'pago': pago, 'cuenta': pago.cuenta, 'titulo_pagina': "Editar Pago"}
    return render(request, 'finanzas/formulario_pago.html', context)


@login_required
@permission_required('finanzas.delete_pagoregistrado', raise_exception=True)
def eliminar_pago(request, pago_id):
    pago = get_object_or_404(PagoRegistrado, id=pago_id, institucion=request.user.institucion_asociada)
    estudiante_id = pago.estudiante.pk

    if request.method == 'POST':
        pago_info = {
            'valor': pago.valor_pagado,
            'fecha': pago.fecha_pago,
            'concepto': pago.cuenta.concepto_pago.nombre_concepto,
            'estudiante': pago.estudiante,
            'institucion': pago.institucion
        }
        
        pago.delete()

        try:
            # --- ✅ Lógica corregida para obtener el email del destinatario ---
            email_destinatario = None
            # Busca el primer familiar (acudiente) asociado al estudiante
            acudiente = pago_info['estudiante'].familiares.first() 
            
            if acudiente and acudiente.usuario and acudiente.usuario.email:
                email_destinatario = acudiente.usuario.email
            elif pago_info['estudiante'].usuario and pago_info['estudiante'].usuario.email:
                # Si no hay acudiente con email, usa el del propio estudiante
                email_destinatario = pago_info['estudiante'].usuario.email
            # --- Fin de la corrección ---

            if email_destinatario:
                asunto = f"Anulación de Registro de Pago - {pago_info['institucion'].nombre}"
                cuerpo_html = render_to_string('finanzas/emails/email_eliminacion_pago.html', {'pago': pago_info})

                enviar_correo_dinamico(
                    institucion=pago_info['institucion'],
                    asunto=asunto,
                    destinatarios=[email_destinatario],
                    html_content=cuerpo_html
                )
                messages.success(request, "El pago ha sido eliminado y se ha notificado al acudiente.")
            else:
                messages.warning(request, "Pago eliminado, pero no se pudo notificar (sin email).")
        
        except Exception as e:
            logger.error(f"Error enviando correo de eliminación de pago: {e}")
            messages.warning(request, f"Pago eliminado, pero ocurrió un error al enviar la notificación: {e}")

        return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=estudiante_id)

    context = {'pago': pago, 'titulo_pagina': "Confirmar Eliminación de Pago"}
    return render(request, 'finanzas/confirmar_eliminacion_pago.html', context)


@login_required
def historial_cuentas_estudiante(request, estudiante_id):
    if request.user.is_superuser:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id, institucion=institucion_usuario)
    
    cuentas = (
        CuentaPorCobrarEstudiante.objects
        .filter(estudiante=estudiante)
        .prefetch_related('pagos__facturas_electronicas')
        .order_by('-fecha_vencimiento_especifica')
    )

    # ¿Está activo el módulo de facturación electrónica para esta institución?
    factura_electronica_activa = False
    try:
        from facturacion_electronica.models import ConfiguracionFactus, FacturaElectronica
        cfg = ConfiguracionFactus.objects.filter(institucion=estudiante.institucion).first()
        factura_electronica_activa = bool(cfg and cfg.operativo)

        # Anotar en cada pago su factura electrónica VALIDADA (si existe),
        # usando el prefetch (sin consultas extra).
        for cuenta in cuentas:
            for pago in cuenta.pagos.all():
                pago.fe_validada = next(
                    (f for f in pago.facturas_electronicas.all()
                     if f.tipo == FacturaElectronica.Tipo.FACTURA
                     and f.estado == FacturaElectronica.Estado.VALIDADA),
                    None,
                )
    except Exception:
        factura_electronica_activa = False

    context = {
        'estudiante': estudiante,
        'historial': cuentas,  # Cambiamos 'cuentas' por 'historial' para que coincida con la plantilla
        'factura_electronica_activa': factura_electronica_activa,
    }

    return render(request, 'finanzas/historial_estudiante.html', context)


# --- SINCRONIZACIÓN Y VISTAS DE ESTUDIANTE ---

@login_required
@permission_required('finanzas.add_cuentaporcobrarestudiante', raise_exception=True)
def sincronizar_cuentas_estudiante(request, estudiante_pk):
    """
    Sincroniza TODAS las cuentas automáticas pendientes para UN SOLO estudiante.
    """
    # (Tu lógica de seguridad para obtener el estudiante se mantiene igual)
    if request.user.is_superuser:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_pk)
    else:
        # ... (resto de tu lógica de seguridad)
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        estudiante = get_object_or_404(Estudiante, pk=estudiante_pk, institucion=institucion_usuario)
    
    try:
        resultado = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)
        if resultado.es_warning:
            messages.warning(
                request,
                f"⚠ Sincronización con problemas para {estudiante.usuario.get_full_name()}: "
                f"{resultado.mensaje}",
            )
        elif resultado.total_cuentas_creadas > 0:
            messages.success(
                request,
                f"Sincronización completa para {estudiante.usuario.get_full_name()}. "
                f"{resultado.resumen()}",
            )
        else:
            messages.info(
                request,
                f"El estado de cuenta de {estudiante.usuario.get_full_name()} "
                "ya está completo y sincronizado.",
            )
    except Exception as e:
        messages.error(request, f"Ocurrió un error durante la sincronización: {e}")

    return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=estudiante.pk)


def _redirect_estado_cuenta_tras_pago(request, estudiante):
    """Vuelve al listado de cuentas según si quien paga es el estudiante o un familiar."""
    if hasattr(request.user, 'familiar') and request.user.familiar.estudiantes_asociados.filter(
        pk=estudiante.pk
    ).exists():
        return redirect('finanzas:familiar_estado_cuenta_estudiante', estudiante_pk=estudiante.pk)
    return redirect('finanzas:mi_estado_de_cuenta')


def _cuenta_accesible_para_pago_online(request, cuenta_pk):
    """
    Cuenta por cobrar que el usuario puede pagar online: titular estudiante o familiar asociado.
    Aplica aislamiento multi-institución: la cuenta debe pertenecer a la misma institución
    del usuario que hace la solicitud.
    """
    institucion = getattr(request.user, 'institucion_asociada', None)
    cuenta = get_object_or_404(
        CuentaPorCobrarEstudiante.objects.select_related(
            'estudiante__usuario', 'institucion', 'concepto_pago'
        ),
        pk=cuenta_pk,
        institucion=institucion,   # aislamiento multi-institución
    )
    estudiante = cuenta.estudiante
    if hasattr(request.user, 'estudiante') and request.user.estudiante.pk == estudiante.pk:
        return cuenta
    if hasattr(request.user, 'familiar') and request.user.familiar.estudiantes_asociados.filter(
        pk=estudiante.pk
    ).exists():
        return cuenta
    return None


def _render_mi_estado_de_cuenta(request, estudiante, *, es_vista_familiar):
    filtro = request.GET.get('filtro') or ''
    qs = estudiante.cuentas_por_cobrar.all().order_by('estado', 'fecha_vencimiento_especifica')
    if filtro == 'PENDIENTE':
        qs = qs.exclude(estado='PAGADO')
    elif filtro == 'PAGADO':
        qs = qs.filter(estado='PAGADO')
    cuentas = list(qs)
    total_deuda_filtrada = sum((c.saldo_pendiente for c in cuentas), Decimal(0))

    institucion = getattr(estudiante, 'institucion', None)
    mp_modo_produccion = getattr(institucion, 'mp_modo_produccion', True) if institucion else True

    context = {
        'estudiante': estudiante,
        'cuentas': cuentas,
        'hoy': timezone.now().date(),
        'titulo_pagina': 'Pagos y estado de cuenta' if es_vista_familiar else 'Mi Estado de Cuenta',
        'filtro_activo': filtro,
        'total_deuda_filtrada': total_deuda_filtrada,
        'es_vista_familiar': es_vista_familiar,
        'mp_modo_produccion': mp_modo_produccion,
        'volver_url': (
            reverse('gestion_academica:portal_familiar_inicio')
            if es_vista_familiar
            else reverse('gestion_academica:dashboard_estudiante')
        ),
    }
    return render(request, 'finanzas/mi_estado_de_cuenta.html', context)


@login_required
def mi_estado_de_cuenta(request):
    estudiante = get_object_or_404(Estudiante, usuario=request.user)
    return _render_mi_estado_de_cuenta(request, estudiante, es_vista_familiar=False)


@login_required
def familiar_estado_cuenta_estudiante(request, estudiante_pk):
    """Portal familiar: ver y pagar pensiones/conceptos del hijo (Mercado Pago)."""
    if not hasattr(request.user, 'familiar'):
        messages.error(request, 'Esta sección es solo para familiares.')
        return redirect('gestion_academica:inicio_academico')
    estudiante = get_object_or_404(
        Estudiante,
        pk=estudiante_pk,
        pk__in=request.user.familiar.estudiantes_asociados.values_list('pk', flat=True),
    )
    return _render_mi_estado_de_cuenta(request, estudiante, es_vista_familiar=True)


# --- FLUJO DE MERCADO PAGO ---

@login_required
def iniciar_pago_mercadopago(request, cuenta_pk):
    from finanzas.models import CuentaPorCobrarEstudiante  # noqa: F401 — claridad

    cuenta = _cuenta_accesible_para_pago_online(request, cuenta_pk)
    if cuenta is None:
        messages.error(request, 'No tienes permiso para pagar esta cuenta.')
        return redirect('gestion_academica:inicio_academico')

    estudiante = cuenta.estudiante

    if cuenta.saldo_pendiente <= 0:
        messages.info(request, 'Esta cuenta ya ha sido pagada.')
        return _redirect_estado_cuenta_tras_pago(request, estudiante)

    institucion = cuenta.institucion
    access_token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test

    if not access_token:
        messages.error(request, 'La pasarela de pagos no está configurada para esta institución.')
        return _redirect_estado_cuenta_tras_pago(request, estudiante)

    sdk = mercadopago.SDK(access_token)

    # ✅ URLs seguras con HTTPS dinámicas (funciona con ngrok)
    success_url = request.build_absolute_uri(reverse('finanzas:pago_respuesta_mp')).replace('http://', 'https://')
    notification_url = request.build_absolute_uri(reverse('finanzas:finanzas_mercadopago_webhook')).replace('http://', 'https://')

    payer_email = (request.user.email or estudiante.usuario.email or '').strip()
    if not payer_email:
        messages.error(request, 'Falta un correo en la cuenta del familiar o del estudiante para la pasarela de pago.')
        return _redirect_estado_cuenta_tras_pago(request, estudiante)

    # En PRODUCCIÓN enviamos el email real del pagador (name/surname/email).
    # En TEST NO enviamos el email real: si ese email pertenece a una cuenta real de
    # Mercado Pago, el checkout la precarga como pagador ("aparece logueado") y bloquea
    # el uso del comprador de prueba. Omitiendo el email, MP usa la sesión del
    # comprador de prueba que el usuario tenga iniciada.
    payer_user = estudiante.usuario
    if institucion.mp_modo_produccion:
        payer_data = {
            'name': payer_user.first_name,
            'surname': payer_user.last_name,
            'email': payer_email,
        }
    else:
        payer_data = {
            'name': payer_user.first_name,
            'surname': payer_user.last_name,
        }

    preference_data = {
        'items': [{
            'title': f'Pago: {cuenta.concepto_pago.nombre_concepto}',
            'quantity': 1,
            'unit_price': float(cuenta.saldo_pendiente),
            'currency_id': 'COP',
        }],
        'payer': payer_data,
        'back_urls': {
            'success': success_url,
            'failure': success_url,
            'pending': success_url,
        },
        'auto_return': 'approved',
        'external_reference': f'CUENTA-{cuenta.pk}-{institucion.pk}',
        'notification_url': notification_url,
    }

    try:
        if hasattr(request.user, 'familiar'):
            request.session['mp_return_familiar_estudiante_pk'] = estudiante.pk
        else:
            request.session.pop('mp_return_familiar_estudiante_pk', None)

        logger.info('Preferencia enviada a MP (modo=%s):\n%s',
                    'PRODUCCIÓN' if institucion.mp_modo_produccion else 'TEST', preference_data)

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get('response', {})

        # Seleccionar la URL correcta según el modo de la institución:
        # · Producción → init_point (checkout real)
        # · Test/Sandbox → sandbox_init_point (checkout de pruebas)
        if institucion.mp_modo_produccion:
            url_pago = preference.get('init_point') or preference.get('sandbox_init_point')
        else:
            url_pago = preference.get('sandbox_init_point') or preference.get('init_point')

        if not url_pago:
            logger.error('Mercado Pago no devolvió una URL de pago. Respuesta: %s', preference)
            raise KeyError("No se encontró 'init_point' ni 'sandbox_init_point' en la respuesta de Mercado Pago.")

        logger.info('Redirigiendo al checkout de MP: %s', url_pago)

        cuenta.mercadopago_preference_id = preference.get('id')
        cuenta.save(update_fields=['mercadopago_preference_id'])

        return redirect(url_pago)

    except Exception as e:
        logger.error('Error creando preferencia de MP: %s', e, exc_info=True)
        messages.error(request, 'Hubo un error al comunicarse con la pasarela de pagos.')
        request.session.pop('mp_return_familiar_estudiante_pk', None)
        return _redirect_estado_cuenta_tras_pago(request, estudiante)


@login_required
def pago_respuesta_mp(request):
    status = request.GET.get('status')
    if status == 'approved':
        messages.success(
            request,
            '¡Tu pago ha sido aprobado! Verás el cambio reflejado en el estado de cuenta.',
        )
    elif status in ('in_process', 'pending'):
        messages.info(request, 'Tu pago está pendiente de confirmación.')
    elif status == 'rejected':
        messages.error(request, 'Tu pago fue rechazado. Por favor, intenta de nuevo.')

    pk = request.session.pop('mp_return_familiar_estudiante_pk', None)
    if pk is not None and hasattr(request.user, 'familiar'):
        if request.user.familiar.estudiantes_asociados.filter(pk=pk).exists():
            return redirect('finanzas:familiar_estado_cuenta_estudiante', estudiante_pk=pk)
    return redirect('finanzas:mi_estado_de_cuenta')


def _find_payment_institution(payment_id):
    """
    Función de ayuda para encontrar la institución correcta iterando sobre sus tokens.
    Retorna (institucion, payment_info) o (None, None).
    """
    # Esta consulta ahora funciona porque 'models' ha sido importado.
    instituciones_con_mp = InstitucionEducativa.objects.filter(
        models.Q(mp_access_token_prod__isnull=False) & ~models.Q(mp_access_token_prod__exact='') |
        models.Q(mp_access_token_test__isnull=False) & ~models.Q(mp_access_token_test__exact='')
    )
    
    for institucion in instituciones_con_mp:
        try:
            token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test
            if not token:
                continue
            sdk = mercadopago.SDK(token)
            payment_info = sdk.payment().get(payment_id)["response"]
            return institucion, payment_info
        except Exception:
            continue
    return None, None


@csrf_exempt
@transaction.atomic
def finanzas_mercadopago_webhook(request):
    """
    Webhook para FINANZAS. Procesa pagos de estudiantes (pensiones, etc.).
    """
    if request.method != 'POST':
        return HttpResponse("Método no permitido", status=405)

    try:
        body = json.loads(request.body)
        if body.get("type") != "payment":
            return HttpResponse(status=200)
        payment_id = body["data"]["id"]
    except (json.JSONDecodeError, KeyError):
        logger.error("Webhook Finanzas: Petición mal formada.")
        return HttpResponse("Petición inválida", status=400)

    try:
        institucion_del_pago, payment_info = _find_payment_institution(payment_id)

        if not payment_info:
            logger.error(f"Webhook Finanzas: No se pudo encontrar el pago {payment_id} en ninguna institución.")
            return HttpResponse("Pago no encontrado", status=404)
        
        if payment_info.get('status') == 'approved':
            external_ref = payment_info.get('external_reference')

            if not external_ref or not re.fullmatch(r"CUENTA-\d+-\d+", str(external_ref)):
                logger.warning(f"Webhook Finanzas: Referencia externa no válida en pago {payment_id}: {external_ref}")
                return HttpResponse("external_reference invalida", status=400)

            _, cuenta_id_str, institucion_id_str = str(external_ref).split('-', 2)
            cuenta_id = int(cuenta_id_str)
            institucion_id = int(institucion_id_str)

            if not institucion_del_pago or institucion_del_pago.pk != institucion_id:
                logger.error(
                    f"Webhook Finanzas: institución inconsistente en pago {payment_id}. "
                    f"detectada={getattr(institucion_del_pago, 'pk', None)} referencia={institucion_id}"
                )
                return HttpResponse("Institucion inconsistente", status=400)

            secret = institucion_mp_webhook_secret(institucion_del_pago)
            data_id = resolve_notification_data_id(request, str(payment_id))
            if not verify_mercadopago_webhook_signature(
                secret,
                data_id=data_id,
                x_request_id=request.META.get("HTTP_X_REQUEST_ID"),
                x_signature_header=request.META.get("HTTP_X_SIGNATURE"),
            ):
                return HttpResponse("Firma webhook invalida", status=403)

            if PagoRegistrado.objects.filter(referencia_transaccion=str(payment_id)).exists():
                logger.info(f"Webhook Finanzas: pago {payment_id} ya registrado (idempotencia).")
                return HttpResponse(status=200)

            cuenta = CuentaPorCobrarEstudiante.objects.select_for_update().get(
                pk=cuenta_id,
                institucion__pk=institucion_id,
            )

            if not PagoRegistrado.objects.filter(referencia_transaccion=str(payment_id)).exists():
                pago_mp = PagoRegistrado.objects.create(
                    cuenta=cuenta,
                    estudiante=cuenta.estudiante,
                    valor_pagado=Decimal(payment_info['transaction_amount']),
                    metodo_pago='MERCADO_PAGO',
                    referencia_transaccion=str(payment_id),
                    institucion=institucion_del_pago
                )
                logger.info(f"Webhook de FINANZAS procesó pago para cuenta #{cuenta.id}")

                # Modo B: emisión automática de factura electrónica (no-op si está apagado).
                # Se hace tras el commit para no emitir si la transacción se revierte.
                try:
                    from facturacion_electronica.emision import disparar_emision_automatica
                    transaction.on_commit(lambda: disparar_emision_automatica(pago_mp))
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Error procesando webhook de FINANZAS: {e}", exc_info=True)
        return HttpResponse("Error interno", status=500)

    return HttpResponse(status=200)

class CuentaPorCobrarEstudianteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CuentaPorCobrarEstudiante
    form_class = CuentaPorCobrarEstudianteForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_cuentas_por_cobrar')
    permission_required = 'finanzas.add_cuentaporcobrarestudiante'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Cuenta por Cobrar"
        return context
    
    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.institucion = self.request.user.institucion_asociada
        
        # Asigna el monto del concepto si no se especifica uno
        if not form.cleaned_data.get('monto_asignado') and form.cleaned_data.get('concepto_pago'):
            form.instance.monto_asignado = form.cleaned_data['concepto_pago'].valor

        messages.success(self.request, "Cuenta por cobrar creada exitosamente.")
        return super().form_valid(form)


class CuentaPorCobrarEstudianteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = CuentaPorCobrarEstudiante
    form_class = CuentaPorCobrarEstudianteForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_cuentas_por_cobrar')
    permission_required = 'finanzas.change_cuentaporcobrarestudiante'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Cuenta por Cobrar"
        return context


class CuentaPorCobrarEstudianteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = CuentaPorCobrarEstudiante
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_cuentas_por_cobrar')
    permission_required = 'finanzas.delete_cuentaporcobrarestudiante'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Confirmar Eliminación de Cuenta"
        return context

# Función de ayuda para que xhtml2pdf encuentre imágenes y CSS
def link_callback(uri, rel):
    """
    Convierte los URI de HTML a rutas del sistema de archivos para que pisa
    pueda encontrar los recursos (imágenes, CSS, etc.).
    Protegida contra path traversal.
    """
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        allowed_root = os.path.realpath(settings.MEDIA_ROOT)
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
        allowed_root = os.path.realpath(settings.STATIC_ROOT)
    else:
        return uri

    real_path = os.path.realpath(path)
    if not real_path.startswith(allowed_root + os.sep) and real_path != allowed_root:
        logger.warning("link_callback: path traversal bloqueado para URI: %s", uri)
        return None
    if not os.path.isfile(real_path):
        return None
    return real_path

@login_required
def generar_recibo_pago(request, pago_id):
    """
    Genera un recibo en PDF para un pago específico.
    """
    # Lógica de seguridad: el admin solo puede ver recibos de su institución
    if request.user.is_superuser:
        pago = get_object_or_404(PagoRegistrado, pk=pago_id)
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        pago = get_object_or_404(PagoRegistrado, pk=pago_id, institucion=institucion_usuario)

    # Contexto para la plantilla del PDF.
    # 'domain' es necesario para resolver el logo y la firma (URLs absolutas).
    context = {
        'pago': pago,
        'institucion': pago.institucion,
        'domain': f'{request.scheme}://{request.get_host()}',
    }

    # Renderizar la plantilla HTML a un string
    template = get_template('finanzas/recibo_pago.html')
    html = template.render(context)

    # Crear el PDF
    response = HttpResponse(content_type='application/pdf')
    # Esta línea hace que el PDF se muestre en el navegador en lugar de descargarse
    response['Content-Disposition'] = f'inline; filename="recibo_{pago.id}.pdf"'

    # Usamos pisa para generar el PDF desde el HTML
    pisa_status = pisa.CreatePDF(
        html, dest=response, link_callback=link_callback
    )

    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF.', status=500)

    return response


@login_required
def generar_volante_matricula(request, estudiante_id):
    """
    Genera un volante en PDF con los conceptos de matrícula pendientes de un estudiante.
    """
    # Lógica de seguridad para obtener al estudiante
    if request.user.is_superuser:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id, institucion=institucion_usuario)

    # Buscamos las cuentas pendientes cuyo tipo de concepto sea "Matrícula"
    cuentas_matricula = CuentaPorCobrarEstudiante.objects.filter(
        estudiante=estudiante,
        concepto_pago__tipo_concepto__nombre__iexact="Matrícula",
        estado__in=['PENDIENTE', 'VENCIDO'] # Solo conceptos no pagados
    )

    if not cuentas_matricula.exists():
        messages.error(request, f"No se encontraron conceptos de matrícula pendientes para el estudiante {estudiante}.")
        return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=estudiante.id)

    # Calculamos el total a pagar sumando los saldos pendientes
    total_a_pagar = sum(cuenta.saldo_pendiente for cuenta in cuentas_matricula)
    
    context = {
        'estudiante': estudiante,
        'cuentas': cuentas_matricula,
        'institucion': estudiante.institucion,
        'total_a_pagar': total_a_pagar,
        'tipo_volante': f"Volante de Matrícula {timezone.now().year}",
        # ... puedes añadir más contexto si tu plantilla lo necesita
    }

    template = get_template('finanzas/volante_pago.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="volante_matricula_{estudiante.pk}.pdf"'

    # Usamos la función link_callback que ya definimos antes para las imágenes
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF del volante.', status=500)
    
    return response                

@login_required
def generar_volante_mensualidad(request, cuenta_id):
    """
    Genera un volante en PDF para una única cuenta por cobrar específica.
    Sirve para mensualidades o cualquier otro cobro individual.
    """
    # Lógica de seguridad para obtener la cuenta
    if request.user.is_superuser:
        cuenta = get_object_or_404(CuentaPorCobrarEstudiante, pk=cuenta_id)
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        cuenta = get_object_or_404(CuentaPorCobrarEstudiante, pk=cuenta_id, institucion=institucion_usuario)

    estudiante = cuenta.estudiante

    from finanzas.pdf_helpers import generar_qr_base64, valor_en_letras
    portal_url = request.build_absolute_uri(reverse('finanzas:mi_estado_de_cuenta'))

    context = {
        'cuenta': cuenta,
        'estudiante': estudiante,
        'cuentas': [cuenta], # La plantilla puede iterar sobre una lista de un solo elemento
        'institucion': estudiante.institucion,
        'total_a_pagar': cuenta.saldo_pendiente,
        'tipo_volante': f"Volante de Pago - {cuenta.concepto_pago.nombre_concepto}",
        # Necesarios para el botón "Pagar en línea" del formato Orden de Pago
        'portal_url': portal_url,
        'domain': f'{request.scheme}://{request.get_host()}',
        'qr_pago': generar_qr_base64(portal_url),
        'total_en_letras': valor_en_letras(cuenta.saldo_pendiente),
    }

    template = get_template('finanzas/pdfs/volante_pago.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="volante_{cuenta.pk}.pdf"'

    # Usamos la función link_callback que ya definimos para las imágenes
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF del volante.', status=500)

    return response


@login_required
def previsualizar_orden_pago(request):
    """Previsualiza la Orden de Pago con datos de EJEMPLO, sin crear cuentas ni enviar correos.

    Usa el concepto seleccionado (GET ?concepto_id=) para mostrar su valor real,
    de modo que el administrador vea cómo se verá el documento antes de facturar.
    """
    from types import SimpleNamespace
    from datetime import date, timedelta
    from finanzas.pdf_helpers import generar_qr_base64, valor_en_letras

    institucion = getattr(request.user, 'institucion_asociada', None)
    if not institucion and request.user.is_superuser:
        institucion = InstitucionEducativa.objects.first()
    if not institucion:
        return HttpResponse("Tu usuario no está asociado a ninguna institución.", status=400)

    concepto_id = request.GET.get('concepto_id')
    concepto = None
    if concepto_id:
        concepto_qs = ConceptoPago.objects.filter(pk=concepto_id)
        if not request.user.is_superuser:
            concepto_qs = concepto_qs.filter(institucion=institucion)
        concepto = concepto_qs.first()

    nombre_concepto = concepto.nombre_concepto if concepto else "Concepto de ejemplo"
    monto = (concepto.valor if concepto and concepto.valor else None) or 200000

    estudiante_demo = SimpleNamespace(
        usuario=SimpleNamespace(get_full_name=lambda: "NOMBRE DEL ESTUDIANTE (EJEMPLO)"),
        grado_actual="GRADO (ejemplo)",
        documento_identidad="0000000000",
    )
    cuenta_demo = SimpleNamespace(
        concepto_pago=SimpleNamespace(nombre_concepto=nombre_concepto),
        fecha_vencimiento_especifica=date.today() + timedelta(days=15),
        saldo_pendiente=monto,
    )

    portal_url = request.build_absolute_uri(reverse('finanzas:mi_estado_de_cuenta'))
    context = {
        'cuenta': cuenta_demo,
        'estudiante': estudiante_demo,
        'cuentas': [cuenta_demo],
        'institucion': institucion,
        'total_a_pagar': monto,
        'tipo_volante': 'Orden de Pago (PREVISUALIZACIÓN)',
        'portal_url': portal_url,
        'domain': f'{request.scheme}://{request.get_host()}',
        'qr_pago': generar_qr_base64(portal_url),
        'total_en_letras': valor_en_letras(monto),
    }

    template = get_template('finanzas/pdfs/volante_pago.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="previsualizacion_orden_pago.pdf"'
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar la previsualización.', status=500)
    return response


@login_required
def estado_pagos_estudiante(request):
    """
    Muestra un reporte que agrupa a los estudiantes por grado.
    Los filtros se aplican sobre la lista de estudiantes.
    """
    # Queryset base de estudiantes, optimizado
    estudiantes_qs = Estudiante.objects.select_related('usuario', 'grado_actual')

    # Aplicar filtro de seguridad por institución
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            estudiantes_qs = estudiantes_qs.filter(institucion=institucion_usuario)
        else:
            estudiantes_qs = Estudiante.objects.none()

    # Obtener los valores de los filtros de la URL
    grado_filter = request.GET.get('grado')
    estudiante_filter = request.GET.get('estudiante')
    estado_filter = request.GET.get('estado')
    institucion_filtro = (
        getattr(request.user, 'institucion_asociada', None)
        if not request.user.is_superuser
        else None
    )
    periodo_obj = _periodo_desde_request(request, institucion_filtro)

    # Aplicar filtros a la lista de estudiantes
    if grado_filter:
        estudiantes_qs = estudiantes_qs.filter(grado_actual__pk=grado_filter)
    if estudiante_filter:
        estudiantes_qs = estudiantes_qs.filter(pk=estudiante_filter)
    if estado_filter:
        estudiantes_qs = estudiantes_qs.filter(cuentas_por_cobrar__estado=estado_filter).distinct()
    if periodo_obj:
        estudiantes_qs = estudiantes_qs.filter(
            cuentas_por_cobrar__concepto_pago__periodo_academico_aplicable=periodo_obj
        ).distinct()
    
    # --- LÓGICA DE AGRUPACIÓN POR GRADO ---
    grados_agrupados = defaultdict(list)
    for estudiante in estudiantes_qs.order_by('grado_actual__nombre', 'usuario__last_name'):
        # Usamos el nombre del grado como llave para agrupar
        # Si no tiene grado, lo ponemos en una categoría especial
        llave_grado = estudiante.grado_actual.nombre if estudiante.grado_actual else "Estudiantes sin Grado Asignado"
        grados_agrupados[llave_grado].append(estudiante)
    
    # Querysets para los dropdowns de los filtros
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        grados_disponibles_qs = Grado.objects.filter(institucion=institucion_usuario)
        estudiantes_disponibles_qs = Estudiante.objects.filter(institucion=institucion_usuario)
    else:
        grados_disponibles_qs = Grado.objects.all()
        estudiantes_disponibles_qs = Estudiante.objects.all()

    context = {
        'grados_agrupados': grados_agrupados.items(), # Pasamos el diccionario agrupado
        'estudiantes_disponibles_filtro': estudiantes_disponibles_qs.select_related('usuario').order_by('usuario__last_name'),
        'grados_disponibles': grados_disponibles_qs.order_by('nombre'),
        'estados_pago': ESTADOS_CUENTA,
        'selected_grado': grado_filter,
        'selected_estudiante': estudiante_filter,
        'selected_estado': estado_filter,
        'periodos_filtro': _periodos_para_filtros(request),
        'selected_periodo': str(periodo_obj.pk) if periodo_obj else '',
        'titulo_pagina': 'Reporte General por Grados'
    }
    return render(request, 'finanzas/estado_pagos.html', context)

# --- CRUD PARA CONCEPTO DE PAGO ---

class ConceptoPagoListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = ConceptoPago
    template_name = 'finanzas/conceptos_pago_lista.html'
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_conceptopago'

    def get_queryset(self):
        from django.db.models import F, OrderBy

        queryset = super().get_queryset()
        return (
            queryset
            .select_related(
                'tipo_concepto',
                'periodo_academico_aplicable',
                'nivel_escolaridad',
                'cuenta_contable',
            )
            .order_by(
                OrderBy(F('nivel_escolaridad__orden'), descending=False, nulls_last=True),
                'nivel_escolaridad__nombre',
                'nombre_concepto',
            )
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Conceptos de Pago"
        context["url_crear"] = reverse_lazy('finanzas:crear_concepto_pago')
        return context

class ConceptoPagoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ConceptoPago
    form_class = ConceptoPagoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_conceptos_pago')
    permission_required = 'finanzas.add_conceptopago'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Concepto de pago creado exitosamente.")
        return super().form_valid(form)

    # ▼▼▼ MÉTODO AÑADIDO PARA SOLUCIONAR EL ERROR ▼▼▼
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Concepto de Pago"
        # Añadimos la URL de cancelación como respaldo para el botón
        context["cancel_url"] = self.success_url 
        return context

class ConceptoPagoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = ConceptoPago
    form_class = ConceptoPagoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_conceptos_pago')
    permission_required = 'finanzas.change_conceptopago'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Concepto de Pago"
        # ▼▼▼ LÍNEA AÑADIDA ▼▼▼
        context["cancel_url"] = self.success_url
        return context

class ConceptoPagoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = ConceptoPago
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_conceptos_pago')
    permission_required = 'finanzas.delete_conceptopago'            

@login_required
def exportar_excel_historial_cuentas(request):
    """
    Exporta el historial de cuentas por cobrar a Excel con formato profesional,
    incluyendo código y nombre de cuenta PUC para trazabilidad contable.
    """
    institucion_usuario = getattr(request.user, 'institucion_asociada', None)

    # Queryset base — include cuenta_contable para PUC
    cuentas_qs = CuentaPorCobrarEstudiante.objects.select_related(
        'estudiante__usuario',
        'estudiante__grado_actual',
        'concepto_pago__cuenta_contable',
        'institucion',
    )

    if not request.user.is_superuser:
        if institucion_usuario:
            cuentas_qs = cuentas_qs.filter(institucion=institucion_usuario)
        else:
            cuentas_qs = CuentaPorCobrarEstudiante.objects.none()

    # Filtros de la URL
    grado_filter       = request.GET.get('grado')
    estudiante_id_filter = request.GET.get('estudiante')
    estado_filter      = request.GET.get('estado')
    periodo_obj = _periodo_desde_request(
        request,
        institucion_usuario if not request.user.is_superuser else None,
    )
    if grado_filter:
        cuentas_qs = cuentas_qs.filter(estudiante__grado_actual__pk=grado_filter)
    if estudiante_id_filter:
        cuentas_qs = cuentas_qs.filter(estudiante__pk=estudiante_id_filter)
    if estado_filter:
        cuentas_qs = cuentas_qs.filter(estado=estado_filter)
    if periodo_obj:
        cuentas_qs = cuentas_qs.filter(concepto_pago__periodo_academico_aplicable=periodo_obj)

    cuentas_qs = cuentas_qs.order_by(
        'estudiante__usuario__last_name',
        'estudiante__usuario__first_name',
        'fecha_vencimiento_especifica',
    )

    # Construir filas incluyendo PUC
    data = []
    for cuenta in cuentas_qs:
        cc = cuenta.concepto_pago.cuenta_contable if cuenta.concepto_pago else None
        data.append({
            'N° Factura':          cuenta.numero_documento or '',
            'Estudiante':          cuenta.estudiante.usuario.get_full_name(),
            'Documento ID':        getattr(cuenta.estudiante, 'documento_identidad', '') or '',
            'Grado':               cuenta.estudiante.grado_actual.nombre if cuenta.estudiante.grado_actual else 'N/A',
            'Concepto de Pago':    cuenta.concepto_pago.nombre_concepto,
            'Código PUC':          cc.codigo if cc else '',
            'Nombre Cuenta PUC':   cc.nombre  if cc else '',
            'Mes':                 cuenta.mes  or '',
            'Año':                 cuenta.año  or '',
            'Monto Asignado':      float(cuenta.monto_asignado),
            'Monto Pagado':        float(cuenta.monto_pagado_actual),
            'Saldo Pendiente':     float(cuenta.saldo_pendiente),
            'Fecha Vencimiento':   cuenta.fecha_vencimiento_especifica.strftime('%Y-%m-%d'),
            'Estado':              cuenta.get_estado_display(),
            'Institución':         cuenta.institucion.nombre,
        })

    df = pd.DataFrame(data) if data else pd.DataFrame(columns=[
        'N° Factura', 'Estudiante', 'Documento ID', 'Grado', 'Concepto de Pago',
        'Código PUC', 'Nombre Cuenta PUC', 'Mes', 'Año',
        'Monto Asignado', 'Monto Pagado', 'Saldo Pendiente',
        'Fecha Vencimiento', 'Estado', 'Institución',
    ])

    # Hoja de resumen
    inst_nombre = institucion_usuario.nombre if institucion_usuario else 'Global'
    inst_nit    = institucion_usuario.nit    if institucion_usuario else ''
    resumen = pd.DataFrame([
        {'Campo': 'Institución',          'Valor': inst_nombre},
        {'Campo': 'NIT',                  'Valor': inst_nit},
        {'Campo': 'Generado el',          'Valor': timezone.now().strftime('%Y-%m-%d %H:%M')},
        {'Campo': 'Generado por',         'Valor': request.user.get_full_name() or request.user.get_username()},
        {'Campo': 'Total registros',      'Valor': len(data)},
        {'Campo': 'Total monto asignado', 'Valor': f"${sum(r['Monto Asignado']  for r in data):,.2f}"},
        {'Campo': 'Total monto pagado',   'Valor': f"${sum(r['Monto Pagado']    for r in data):,.2f}"},
        {'Campo': 'Total saldo pendiente','Valor': f"${sum(r['Saldo Pendiente'] for r in data):,.2f}"},
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book

        # ── Formatos ──────────────────────────────────────────────
        fmt_header = wb.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#0F3460',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'text_wrap': True,
        })
        fmt_puc_header = wb.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#1B5E20',
            'border': 1, 'align': 'center', 'valign': 'vcenter',
            'text_wrap': True,
        })
        fmt_money   = wb.add_format({'num_format': '$#,##0.00', 'border': 1})
        fmt_money_r = wb.add_format({'num_format': '$#,##0.00', 'border': 1, 'bold': True})
        fmt_cell    = wb.add_format({'border': 1, 'valign': 'vcenter'})
        fmt_puc_code = wb.add_format({
            'border': 1, 'font_color': '#075985', 'bg_color': '#E0F2FE',
            'bold': True, 'font_name': 'Courier New', 'font_size': 9,
        })
        fmt_puc_empty = wb.add_format({
            'border': 1, 'font_color': '#94A3B8', 'italic': True,
        })
        fmt_even    = wb.add_format({'border': 1, 'bg_color': '#F8FAFF', 'valign': 'vcenter'})
        fmt_money_even = wb.add_format({'num_format': '$#,##0.00', 'border': 1, 'bg_color': '#F8FAFF'})
        fmt_total   = wb.add_format({
            'bold': True, 'num_format': '$#,##0.00', 'bg_color': '#0F3460',
            'font_color': 'white', 'border': 1,
        })
        fmt_total_lbl = wb.add_format({
            'bold': True, 'bg_color': '#0F3460', 'font_color': 'white', 'border': 1,
        })

        # ── HOJA: Cuentas por Cobrar ──────────────────────────────
        df.to_excel(writer, index=False, sheet_name='Cuentas por Cobrar', startrow=2)
        ws = writer.sheets['Cuentas por Cobrar']

        # Título
        ws.merge_range('A1:O1', f'Reporte de Cuentas por Cobrar — {inst_nombre}',
                       wb.add_format({'bold': True, 'font_size': 13, 'font_color': '#0F3460',
                                      'bg_color': '#E8EEF8', 'border': 1, 'align': 'center'}))

        # Cabeceras con color: PUC en verde oscuro, resto en azul
        cols = list(df.columns)
        puc_cols = {'Código PUC', 'Nombre Cuenta PUC'}
        for col_idx, col_name in enumerate(cols):
            fmt = fmt_puc_header if col_name in puc_cols else fmt_header
            ws.write(2, col_idx, col_name, fmt)

        # Filas de datos
        money_cols = {'Monto Asignado', 'Monto Pagado', 'Saldo Pendiente'}
        for row_idx, row in enumerate(data):
            is_even = row_idx % 2 == 0
            for col_idx, col_name in enumerate(cols):
                val = row[col_name]
                if col_name in money_cols:
                    fmt_use = fmt_money_even if is_even else fmt_money
                    ws.write(row_idx + 3, col_idx, val, fmt_use)
                elif col_name == 'Código PUC':
                    ws.write(row_idx + 3, col_idx, val,
                             fmt_puc_code if val else fmt_puc_empty)
                elif col_name == 'Nombre Cuenta PUC':
                    ws.write(row_idx + 3, col_idx, val,
                             fmt_even if is_even else fmt_cell)
                else:
                    ws.write(row_idx + 3, col_idx, val,
                             fmt_even if is_even else fmt_cell)

        # Fila de totales
        total_row = len(data) + 3
        ws.write(total_row, cols.index('Estudiante'), 'TOTALES', fmt_total_lbl)
        ws.write(total_row, cols.index('Monto Asignado'),  sum(r['Monto Asignado']  for r in data), fmt_total)
        ws.write(total_row, cols.index('Monto Pagado'),    sum(r['Monto Pagado']    for r in data), fmt_total)
        ws.write(total_row, cols.index('Saldo Pendiente'), sum(r['Saldo Pendiente'] for r in data), fmt_total)

        # Anchos de columna
        col_widths = {
            'N° Factura': 10, 'Estudiante': 28, 'Documento ID': 14, 'Grado': 14,
            'Concepto de Pago': 28, 'Código PUC': 12, 'Nombre Cuenta PUC': 32,
            'Mes': 6, 'Año': 6, 'Monto Asignado': 16, 'Monto Pagado': 16,
            'Saldo Pendiente': 16, 'Fecha Vencimiento': 16, 'Estado': 14, 'Institución': 24,
        }
        for col_idx, col_name in enumerate(cols):
            ws.set_column(col_idx, col_idx, col_widths.get(col_name, 14))
        ws.set_row(2, 30)  # altura cabecera
        ws.freeze_panes(3, 0)

        # ── HOJA: Resumen ─────────────────────────────────────────
        resumen.to_excel(writer, index=False, sheet_name='Resumen', startrow=1)
        ws2 = writer.sheets['Resumen']
        ws2.merge_range('A1:B1', f'Resumen — {inst_nombre}',
                        wb.add_format({'bold': True, 'font_size': 12, 'font_color': '#0F3460',
                                       'bg_color': '#E8EEF8', 'border': 1, 'align': 'center'}))
        ws2.write(1, 0, 'Campo',  fmt_header)
        ws2.write(1, 1, 'Valor',  fmt_header)
        for i, (_, row) in enumerate(resumen.iterrows()):
            ws2.write(i + 2, 0, row['Campo'], fmt_cell)
            ws2.write(i + 2, 1, row['Valor'], fmt_cell)
        ws2.set_column(0, 0, 28)
        ws2.set_column(1, 1, 40)

    output.seek(0)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="Reporte_Cuentas_por_Cobrar.xlsx"'
    return response

class CategoriaGastoListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = CategoriaGasto
    template_name = 'finanzas/listado_configuracion.html'
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_categoriagasto' # Permiso autogenerado por Django

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Categorías de Gastos"
        context["url_crear"] = reverse_lazy('finanzas:crear_categoria_gasto')
        # Añadimos una pista para que la plantilla genérica sepa qué columnas mostrar
        context["tipo_listado"] = "categoria_gasto"
        return context
    
class CategoriaGastoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_categorias_gasto')
    permission_required = 'finanzas.add_categoriagasto'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Categoría de gasto creada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Categoría de Gasto"
        context["cancel_url"] = self.success_url
        return context 

# =================================================================
# === NUEVO CRUD PARA TIPO DE GASTO ===
# =================================================================
class TipoGastoListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = TipoGasto
    template_name = 'finanzas/listado_configuracion.html'
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_tipogasto' # Django crea este permiso automáticamente

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Tipos de Gasto"
        context["url_crear"] = reverse_lazy('finanzas:crear_tipo_gasto')
        context["tipo_listado"] = "tipo_gasto" # Pista para la plantilla
        return context

class TipoGastoCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TipoGasto
    form_class = TipoGastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_tipos_gasto')
    permission_required = 'finanzas.add_tipogasto'

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Tipo de gasto creado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Nuevo Tipo de Gasto"
        context["cancel_url"] = self.success_url
        return context

class TipoGastoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = TipoGasto
    form_class = TipoGastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_tipos_gasto')
    permission_required = 'finanzas.change_tipogasto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Tipo de Gasto"
        context["cancel_url"] = self.success_url
        return context

class TipoGastoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = TipoGasto
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_tipos_gasto')
    permission_required = 'finanzas.delete_tipogasto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Eliminar Tipo de Gasto"
        return context         



class CategoriaGastoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_categorias_gasto')
    permission_required = 'finanzas.change_categoriagasto'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Categoría de Gasto"
        context["cancel_url"] = self.success_url
        return context
    
class CategoriaGastoDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = CategoriaGasto
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_categorias_gasto')
    permission_required = 'finanzas.delete_categoriagasto'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Eliminar Categoría de Gasto"
        return context    


# --- CRUD PARA PROVEEDOR ---


class ProveedorListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = Proveedor
    template_name = 'finanzas/listado_configuracion.html' # Reutilizamos la plantilla
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_proveedor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Proveedores"
        context["url_crear"] = reverse_lazy('finanzas:crear_proveedor')
        context["tipo_listado"] = "proveedor" # Pista para la plantilla
        return context

class ProveedorCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_proveedores')
    permission_required = 'finanzas.add_proveedor'

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Proveedor creado exitosamente.")
        return super().form_valid(form)

    # ▼▼▼ MÉTODO AÑADIDO ▼▼▼
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Nuevo Proveedor"
        context["cancel_url"] = self.success_url
        return context

class ProveedorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = Proveedor
    form_class = ProveedorForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_proveedores')
    permission_required = 'finanzas.change_proveedor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Proveedor"
        context["cancel_url"] = self.success_url
        return context

class ProveedorDeleteView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = Proveedor
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_proveedores')
    permission_required = 'finanzas.delete_proveedor'


# --- CRUD PARA GASTO ---

class GastoListView(LoginRequiredMixin, InstitucionOwnedMixin, ListView):
    model = Gasto
    template_name = 'finanzas/gasto_list.html' # Necesitaremos una plantilla específica
    context_object_name = 'gastos'

    def get_queryset(self):
        return Gasto.objects.filter(institucion=self.request.user.institucion_asociada)


class GastoCreateView(LoginRequiredMixin, CreateView):
    model = Gasto
    form_class = GastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_gastos')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        form.instance.registrado_por = self.request.user
        messages.success(self.request, "Gasto registrado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Registrar Nuevo Gasto"
        context["cancel_url"] = self.success_url
        return context

class GastoUpdateView(LoginRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = Gasto
    form_class = GastoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_gastos')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Gasto"
        context["cancel_url"] = self.success_url
        return context

class GastoDeleteView(LoginRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = Gasto
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_gastos') 

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Eliminar Gasto"
        context["cancel_url"] = self.success_url
        return context   

@login_required
def reporte_estado_resultados(request):
    """
    Calcula y muestra el estado de resultados (Ingresos vs. Gastos)
    y prepara los datos para un gráfico de los últimos 6 meses.
    """
    # Importamos json dentro de la función para evitar cargarlo si no se usa
    import json
    from calendar import month_name

    # --- Lógica de Filtros ---
    today = date.today()
    fecha_fin_defecto = today.strftime('%Y-%m-%d')
    fecha_inicio_defecto = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    fecha_inicio = request.GET.get('fecha_inicio', fecha_inicio_defecto)
    fecha_fin = request.GET.get('fecha_fin', fecha_fin_defecto)

    # --- QuerySet Base con Seguridad Multi-institución ---
    pagos_qs = PagoRegistrado.objects.all()
    gastos_qs = Gasto.objects.all()
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            pagos_qs = pagos_qs.filter(institucion=institucion_usuario)
            gastos_qs = gastos_qs.filter(institucion=institucion_usuario)
        else:
            # Si no tiene institución, los querysets quedan vacíos
            pagos_qs = PagoRegistrado.objects.none()
            gastos_qs = Gasto.objects.none()

    periodo_obj = _periodo_desde_request(
        request,
        getattr(request.user, 'institucion_asociada', None) if not request.user.is_superuser else None,
    )
    pagos_qs = _filtrar_pagos_por_periodo(pagos_qs, periodo_obj)

    # --- Cálculos para las tarjetas de resumen ---
    pagos_en_rango = pagos_qs.filter(fecha_pago__range=[fecha_inicio, fecha_fin])
    gastos_en_rango = gastos_qs.filter(fecha_gasto__range=[fecha_inicio, fecha_fin])
    total_ingresos = pagos_en_rango.aggregate(total=Sum('valor_pagado'))['total'] or 0
    total_gastos = gastos_en_rango.aggregate(total=Sum('monto'))['total'] or 0
    utilidad_neta = total_ingresos - total_gastos

    # --- Lógica para los Datos del Gráfico ---
    chart_labels = []
    chart_ingresos = []
    chart_gastos = []

    for i in range(5, -1, -1):
        mes = (today.month - i - 1) % 12 + 1
        año = today.year + (today.month - i - 1) // 12
        
        # Obtenemos el nombre del mes en español
        nombres_meses_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        chart_labels.append(f"{nombres_meses_es[mes]} {año}")

        ingresos_mes = pagos_qs.filter(fecha_pago__year=año, fecha_pago__month=mes).aggregate(total=Sum('valor_pagado'))['total'] or 0
        chart_ingresos.append(float(ingresos_mes))

        gastos_mes = gastos_qs.filter(fecha_gasto__year=año, fecha_gasto__month=mes).aggregate(total=Sum('monto'))['total'] or 0
        chart_gastos.append(float(gastos_mes))
    
    context = {
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'utilidad_neta': utilidad_neta,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'titulo_pagina': 'Estado de Resultados',
        # Pasamos los datos del gráfico a la plantilla
        'chart_labels': json.dumps(chart_labels),
        'chart_ingresos': json.dumps(chart_ingresos),
        'chart_gastos': json.dumps(chart_gastos),
        'periodos_filtro': _periodos_para_filtros(request),
        'selected_periodo': str(periodo_obj.pk) if periodo_obj else '',
        'periodo_filtrado': periodo_obj,
    }
    return render(request, 'finanzas/reporte_estado_resultados.html', context)

@login_required
def reporte_cartera_por_edades(request):
    """
    Calcula y muestra la cartera vencida, con filtros funcionales por Grado y Estudiante.
    """
    today = date.today()
    
    # --- 1. Obtener valores de los filtros ---
    # Usamos .get() para obtener los valores de la URL, si no existen, serán None.
    grado_id = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')

    # --- 2. Preparar QuerySet base con seguridad ---
    base_qs = CuentaPorCobrarEstudiante.objects.all()
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        base_qs = base_qs.filter(institucion=institucion_usuario)
        # Querysets para los menús desplegables
        grados_para_filtro = Grado.objects.filter(institucion=institucion_usuario)
        estudiantes_para_filtro = Estudiante.objects.filter(institucion=institucion_usuario).select_related('usuario')
    else:
        grados_para_filtro = Grado.objects.all()
        estudiantes_para_filtro = Estudiante.objects.all().select_related('usuario')

    # --- 3. Aplicar filtros al QuerySet base ---
    if grado_id and grado_id != '':
        base_qs = base_qs.filter(estudiante__grado_actual__id=grado_id)
    
    # ▼▼▼ LÍNEA CORREGIDA ▼▼▼
    if estudiante_id and estudiante_id != '':
        # Cambiamos 'estudiante__id' por 'estudiante' o 'estudiante__pk'
        base_qs = base_qs.filter(estudiante=estudiante_id)
    # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲

    periodo_obj = _periodo_desde_request(
        request,
        getattr(request.user, 'institucion_asociada', None) if not request.user.is_superuser else None,
    )
    if periodo_obj:
        base_qs = base_qs.filter(concepto_pago__periodo_academico_aplicable=periodo_obj)

    # --- 4. El resto de la lógica de cálculo (sin cambios) ---
    # Todos los cálculos ahora se harán sobre el queryset ya filtrado.
    dias_30, dias_60, dias_90 = today - timedelta(days=30), today - timedelta(days=60), today - timedelta(days=90)
    cuentas_vencidas = base_qs.annotate(
        total_pagado=Coalesce(Sum('pagos__valor_pagado'), 0, output_field=DecimalField())
    ).annotate(
        saldo_pendiente_calc=F('monto_asignado') - F('total_pagado')
    ).filter(saldo_pendiente_calc__gt=0, fecha_vencimiento_especifica__lt=today)

    detalle_cartera = cuentas_vencidas.annotate(dias_vencido=today - F('fecha_vencimiento_especifica')).order_by('-dias_vencido')
    resumen_cartera = detalle_cartera.aggregate(
        total_vencido=Sum('saldo_pendiente_calc'),
        de_1_a_30_dias=Sum(Case(When(fecha_vencimiento_especifica__gte=dias_30, then='saldo_pendiente_calc'), default=0, output_field=DecimalField())),
        de_31_a_60_dias=Sum(Case(When(fecha_vencimiento_especifica__lt=dias_30, fecha_vencimiento_especifica__gte=dias_60, then='saldo_pendiente_calc'), default=0, output_field=DecimalField())),
        de_61_a_90_dias=Sum(Case(When(fecha_vencimiento_especifica__lt=dias_60, fecha_vencimiento_especifica__gte=dias_90, then='saldo_pendiente_calc'), default=0, output_field=DecimalField())),
        mas_de_90_dias=Sum(Case(When(fecha_vencimiento_especifica__lt=dias_90, then='saldo_pendiente_calc'), default=0, output_field=DecimalField()))
    )
    
    context = {
        'resumen': resumen_cartera,
        'detalle_cartera': detalle_cartera,
        'grados_filtro': grados_para_filtro.order_by('nombre'),
        'estudiantes_filtro': estudiantes_para_filtro.order_by('usuario__last_name'),
        'selected_grado': grado_id,
        'selected_estudiante': estudiante_id,
        'periodos_filtro': _periodos_para_filtros(request),
        'selected_periodo': str(periodo_obj.pk) if periodo_obj else '',
        'periodo_filtrado': periodo_obj,
        'titulo_pagina': 'Reporte de Cartera por Edades'
    }
    return render(request, 'finanzas/reporte_cartera.html', context)

@login_required
def reporte_flujo_caja(request):
    """
    Calcula y muestra el flujo de caja. Tanto los resúmenes numéricos como el gráfico
    se actualizan según el rango de fechas seleccionado.
    """
    today = date.today()
    fecha_inicio_defecto = today.replace(day=1).strftime('%Y-%m-%d')
    fecha_fin_defecto = (today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    fecha_fin_defecto = fecha_fin_defecto.strftime('%Y-%m-%d')

    fecha_inicio_str = request.GET.get('fecha_inicio', fecha_inicio_defecto)
    fecha_fin_str = request.GET.get('fecha_fin', fecha_fin_defecto)

    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()

    # QuerySets base con seguridad
    if request.user.is_superuser:
        pagos_qs = PagoRegistrado.objects.all()
        gastos_qs = Gasto.objects.all()
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            pagos_qs = PagoRegistrado.objects.filter(institucion=institucion_usuario)
            gastos_qs = Gasto.objects.filter(institucion=institucion_usuario)
        else:
            pagos_qs = PagoRegistrado.objects.none()
            gastos_qs = Gasto.objects.none()

    periodo_obj = _periodo_desde_request(
        request,
        getattr(request.user, 'institucion_asociada', None) if not request.user.is_superuser else None,
    )
    pagos_qs = _filtrar_pagos_por_periodo(pagos_qs, periodo_obj)

    # 1. Cálculos para las tarjetas de resumen (sin cambios)
    ingresos_anteriores = pagos_qs.filter(fecha_pago__lt=fecha_inicio).aggregate(total=Sum('valor_pagado'))['total'] or Decimal('0.00')
    gastos_anteriores = gastos_qs.filter(fecha_gasto__lt=fecha_inicio).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_inicial = ingresos_anteriores - gastos_anteriores
    ingresos_periodo = pagos_qs.filter(fecha_pago__range=[fecha_inicio, fecha_fin]).aggregate(total=Sum('valor_pagado'))['total'] or Decimal('0.00')
    gastos_periodo = gastos_qs.filter(fecha_gasto__range=[fecha_inicio, fecha_fin]).aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
    saldo_final = saldo_inicial + ingresos_periodo - gastos_periodo

    # --- 2. NUEVA LÓGICA PARA LOS DATOS DEL GRÁFICO DINÁMICO ---
    # Agrupamos todos los ingresos y gastos por día dentro del rango
    movimientos_diarios = defaultdict(Decimal)
    
    ingresos_diarios = pagos_qs.filter(fecha_pago__range=[fecha_inicio, fecha_fin]) \
                               .values('fecha_pago').annotate(total_dia=Sum('valor_pagado'))
    for ingreso in ingresos_diarios:
        movimientos_diarios[ingreso['fecha_pago']] += ingreso['total_dia']

    gastos_diarios = gastos_qs.filter(fecha_gasto__range=[fecha_inicio, fecha_fin]) \
                             .values('fecha_gasto').annotate(total_dia=Sum('monto'))
    for gasto in gastos_diarios:
        movimientos_diarios[gasto['fecha_gasto']] -= gasto['total_dia']

    # Creamos la serie de datos para el gráfico
    chart_labels = []
    chart_saldos = []
    saldo_corriente = saldo_inicial
    
    # Iteramos por cada día en el rango de fechas seleccionado
    current_date = fecha_inicio
    while current_date <= fecha_fin:
        chart_labels.append(current_date.strftime('%d-%b'))
        # Sumamos el movimiento neto del día al saldo
        saldo_corriente += movimientos_diarios.get(current_date, Decimal('0.00'))
        chart_saldos.append(float(saldo_corriente))
        current_date += timedelta(days=1)

    context = {
        'saldo_inicial': saldo_inicial,
        'ingresos_periodo': ingresos_periodo,
        'gastos_periodo': gastos_periodo,
        'saldo_final': saldo_final,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'titulo_pagina': 'Reporte de Flujo de Caja',
        'chart_labels': json.dumps(chart_labels),
        'chart_saldos': json.dumps(chart_saldos),
        'periodos_filtro': _periodos_para_filtros(request),
        'selected_periodo': str(periodo_obj.pk) if periodo_obj else '',
        'periodo_filtrado': periodo_obj,
    }
    return render(request, 'finanzas/reporte_flujo_caja.html', context)

class DescuentoListView(LoginRequiredMixin, InstitucionOwnedMixin, ListView):
    model = Descuento
    template_name = 'finanzas/listado_configuracion.html'
    context_object_name = 'objetos'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Descuentos y Becas"
        context["url_crear"] = reverse_lazy('finanzas:crear_descuento')
        context["tipo_listado"] = "descuento" # Pista para la plantilla
        return context

class DescuentoCreateView(LoginRequiredMixin, CreateView):
    model = Descuento
    form_class = DescuentoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_descuentos')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Descuento creado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Crear Nuevo Descuento"
        context["cancel_url"] = self.success_url
        return context

class DescuentoUpdateView(LoginRequiredMixin, InstitucionOwnedMixin, UpdateView):
    model = Descuento
    form_class = DescuentoForm
    template_name = 'finanzas/formulario_generico.html'
    success_url = reverse_lazy('finanzas:lista_descuentos')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar Descuento"
        context["cancel_url"] = self.success_url
        return context

class DescuentoDeleteView(LoginRequiredMixin, InstitucionOwnedMixin, DeleteView):
    model = Descuento
    template_name = 'finanzas/confirmar_eliminacion.html'
    success_url = reverse_lazy('finanzas:lista_descuentos')    

@login_required
@permission_required('finanzas.add_cuentaporcobrarestudiante')
def facturacion_masiva(request):
    from .tasks import enviar_avisos_cobro_masivo_task

    institucion = getattr(request.user, 'institucion_asociada', None)
    if not institucion:
        messages.error(request, "Tu usuario no está asociado a ninguna institución.")
        return redirect('finanzas:dashboard_financiero')

    if request.method == 'POST':
        form = FacturacionMasivaForm(request.POST, user=request.user)
        if form.is_valid():
            concepto = form.cleaned_data['concepto_pago']
            grados = form.cleaned_data['grados']
            toda_la_institucion = form.cleaned_data['toda_la_institucion']
            fecha_vencimiento = form.cleaned_data['fecha_vencimiento']
            notificar_correo = form.cleaned_data.get('notificar_correo', True)

            if toda_la_institucion:
                estudiantes_a_facturar = Estudiante.objects.filter(institucion=institucion, activo=True)
            else:
                estudiantes_a_facturar = Estudiante.objects.filter(
                    institucion=institucion, grado_actual__in=grados, activo=True
                )

            año_cobro = fecha_vencimiento.year
            mes_cobro = fecha_vencimiento.month

            creadas = 0
            existentes = 0
            ids_nuevas = []

            for estudiante in estudiantes_a_facturar:
                monto_final, observaciones = aplicar_descuentos_a_cuenta(estudiante, concepto)
                cuenta, created = CuentaPorCobrarEstudiante.objects.get_or_create(
                    estudiante=estudiante,
                    concepto_pago=concepto,
                    año=año_cobro,
                    mes=mes_cobro,
                    defaults={
                        'monto_asignado': monto_final,
                        'fecha_vencimiento_especifica': fecha_vencimiento,
                        'institucion': institucion,
                        'observaciones_internas': observaciones,
                    }
                )
                if created:
                    creadas += 1
                    ids_nuevas.append(cuenta.pk)
                else:
                    existentes += 1

            msg = (
                f"Proceso completado: Se crearon {creadas} nuevas cuentas. "
                f"{existentes} estudiantes ya tenían este cobro para {mes_cobro}/{año_cobro}."
            )

            if notificar_correo and ids_nuevas:
                if institucion.email_host_user and institucion.email_host_password:
                    portal_url = request.build_absolute_uri(reverse('finanzas:mi_estado_de_cuenta'))
                    domain = request.build_absolute_uri('/')
                    # Si también se emite FE, retrasamos el correo 2 min para que
                    # Factus ya haya validado las facturas antes de adjuntarlas.
                    email_countdown = 120 if request.POST.get('emitir_factura_electronica') else 0
                    enviar_avisos_cobro_masivo_task.apply_async(
                        kwargs=dict(
                            cuenta_ids=ids_nuevas,
                            institucion_id=institucion.pk,
                            portal_url=portal_url,
                            domain=domain,
                        ),
                        countdown=email_countdown,
                    )
                    msg += f" Enviando {creadas} notificaciones por correo en segundo plano."
                else:
                    msg += " (Correos no enviados: configure el servidor SMTP en Ajustes de la institución.)"

            # ── Facturación electrónica al CAUSAR el cobro (Parte 3) ──
            # Si el módulo está operativo y el admin marcó "emitir factura electrónica",
            # se emite una factura DIAN por cada cuenta nueva, al acudiente, en background.
            if ids_nuevas and request.POST.get('emitir_factura_electronica'):
                try:
                    from facturacion_electronica.models import ConfiguracionFactus
                    cfg = ConfiguracionFactus.objects.filter(institucion=institucion).first()
                    if cfg and cfg.operativo:
                        from facturacion_electronica.tasks import emitir_facturas_masivas_async
                        emitir_facturas_masivas_async.delay(ids_nuevas)
                        msg += f" Emitiendo {creadas} factura(s) electrónica(s) al acudiente en segundo plano."
                    else:
                        msg += " (Factura electrónica NO emitida: el módulo no está activo/operativo.)"
                except Exception as exc:
                    logger.error("Facturación masiva: no se pudo encolar FE: %s", exc, exc_info=True)

            messages.success(request, msg)
            if ids_nuevas:
                request.session['facturacion_masiva_ultimo_lote'] = ids_nuevas
            return redirect('facturacion_electronica:lista_facturas')
    else:
        form = FacturacionMasivaForm(user=request.user)

    # Cuentas del último lote (si vienen de un POST reciente)
    ultimo_lote_ids = request.session.pop('facturacion_masiva_ultimo_lote', None)
    if ultimo_lote_ids:
        ultimo_lote = (
            CuentaPorCobrarEstudiante.objects
            .filter(pk__in=ultimo_lote_ids, institucion=institucion)
            .select_related('estudiante__usuario', 'concepto_pago')
            .order_by('estudiante__usuario__last_name')
        )
    else:
        ultimo_lote = None

    # Últimas 40 cuentas creadas para la institución (historial visible)
    cuentas_recientes = (
        CuentaPorCobrarEstudiante.objects
        .filter(institucion=institucion)
        .select_related('estudiante__usuario', 'concepto_pago')
        .order_by('-fecha_creacion')[:40]
    )

    smtp_ok = bool(institucion.email_host_user and institucion.email_host_password)

    # ¿Módulo de facturación electrónica operativo? (para mostrar la opción)
    fe_operativo = False
    try:
        from facturacion_electronica.models import ConfiguracionFactus
        cfg = ConfiguracionFactus.objects.filter(institucion=institucion).first()
        fe_operativo = bool(cfg and cfg.operativo)
    except Exception:
        fe_operativo = False

    context = {
        'form': form,
        'titulo_pagina': 'Facturación Masiva',
        'smtp_configurado': smtp_ok,
        'ultimo_lote': ultimo_lote,
        'cuentas_recientes': cuentas_recientes,
        'fe_operativo': fe_operativo,
    }
    return render(request, 'finanzas/facturacion_masiva.html', context)



@login_required
def exportacion_contable(request):
    if not _puede_exportacion_contable(request.user):
        messages.error(request, "No tiene permisos para exportar información contable.")
        return redirect("finanzas:reportes_exportaciones")

    institucion = getattr(request.user, "institucion_asociada", None)
    if not institucion:
        messages.error(request, "Debe tener una institución asociada para exportar movimientos contables.")
        return redirect("finanzas:reportes_exportaciones")

    if request.method == "POST":
        form = ExportacionContableForm(request.POST, inst=institucion)
        if form.is_valid():
            fecha_inicio = form.cleaned_data["fecha_inicio"]
            fecha_fin = form.cleaned_data["fecha_fin"]
            tipo_transaccion = form.cleaned_data["tipo_transaccion"]
            formato = form.cleaned_data.get("formato") or "XLSX"
            periodo_sel = form.cleaned_data.get("periodo_academico")

            movimientos = _movimientos_contables_rango(
                institucion,
                fecha_inicio,
                fecha_fin,
                tipo_transaccion,
                periodo_sel,
            )

            df_mov = pd.DataFrame(movimientos)

            total_cred = sum((m["Crédito"] for m in movimientos), Decimal("0.00"))
            total_deb = sum((m["Débito"] for m in movimientos), Decimal("0.00"))

            generado_en = timezone.now()
            resumen_rows = [
                {"Campo": "Institución", "Valor": institucion.nombre},
                {"Campo": "NIT", "Valor": institucion.nit},
                {"Campo": "Rango exportado", "Valor": f"{fecha_inicio} a {fecha_fin}"},
                {"Campo": "Tipo de movimientos", "Valor": tipo_transaccion},
                {
                    "Campo": "Periodo académico (filtro ingresos)",
                    "Valor": str(periodo_sel) if periodo_sel else "Todos",
                },
                {"Campo": "Generado el", "Valor": generado_en.strftime("%Y-%m-%d %H:%M:%S %Z")},
                {
                    "Campo": "Generado por",
                    "Valor": request.user.get_username(),
                },
                {"Campo": "Nombre usuario", "Valor": request.user.get_full_name() or ""},
                {"Campo": "Registros exportados", "Valor": len(movimientos)},
                {"Campo": "Total créditos (ingresos)", "Valor": str(total_cred)},
                {"Campo": "Total débitos (gastos)", "Valor": str(total_deb)},
            ]
            df_resumen = pd.DataFrame(resumen_rows)

            slug = f"Exportacion_Contable_{fecha_inicio}_{fecha_fin}"

            if formato == "CSV":
                buf = io.StringIO()
                df_resumen.to_csv(buf, index=False, sep=";", encoding="utf-8")
                buf.write("\n")
                if not df_mov.empty:
                    df_mov.to_csv(buf, index=False, sep=";", encoding="utf-8")
                data = "\ufeff" + buf.getvalue()
                response = HttpResponse(data, content_type="text/csv; charset=utf-8")
                response["Content-Disposition"] = f'attachment; filename="{slug}.csv"'
                AuditoriaExportacionContable.objects.create(
                    institucion=institucion,
                    usuario=request.user,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    tipo_transaccion=tipo_transaccion,
                    formato=formato,
                    periodo_academico=periodo_sel,
                    registros=len(movimientos),
                )
                return response

            if formato == "PDF":
                tpl = get_template("finanzas/pdfs/exportacion_contable_resumen.html")
                html = tpl.render(
                    {
                        "institucion": institucion,
                        "resumen_filas": resumen_rows,
                    }
                )
                response = HttpResponse(content_type="application/pdf")
                pdf_name = f"Resumen_Exportacion_Contable_{fecha_inicio}_{fecha_fin}.pdf"
                response["Content-Disposition"] = f'attachment; filename="{pdf_name}"'
                pisa_status = pisa.CreatePDF(
                    html, dest=response, link_callback=link_callback
                )
                if pisa_status.err:
                    logger.error(
                        "Error PDF resumen exportación contable: %s", pisa_status.err
                    )
                    messages.error(
                        request,
                        "No se pudo generar el PDF de resumen. Intente de nuevo o use Excel/CSV.",
                    )
                    return redirect("finanzas:exportacion_contable")
                AuditoriaExportacionContable.objects.create(
                    institucion=institucion,
                    usuario=request.user,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    tipo_transaccion=tipo_transaccion,
                    formato=formato,
                    periodo_academico=periodo_sel,
                    registros=len(movimientos),
                )
                return response

            # Reordenar columnas del DataFrame para que PUC quede visible al inicio
            columnas_orden = [
                "Fecha", "Tipo", "Código PUC", "Nombre cuenta PUC",
                "Concepto", "Documento tercero", "Nombre tercero",
                "Método de pago", "Referencia transacción",
                "N° recibo / documento", "Observación",
                "Débito", "Crédito", "ID interno",
            ]
            if not df_mov.empty:
                cols_presentes = [c for c in columnas_orden if c in df_mov.columns]
                df_mov = df_mov[cols_presentes]

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                wb = writer.book

                # ── Formatos ──────────────────────────────────────
                fmt_hdr = wb.add_format({
                    "bold": True, "font_color": "white", "bg_color": "#0F3460",
                    "border": 1, "align": "center", "valign": "vcenter", "text_wrap": True,
                })
                fmt_hdr_puc = wb.add_format({
                    "bold": True, "font_color": "white", "bg_color": "#1B5E20",
                    "border": 1, "align": "center", "valign": "vcenter",
                })
                fmt_cell  = wb.add_format({"border": 1, "valign": "vcenter"})
                fmt_even  = wb.add_format({"border": 1, "bg_color": "#F8FAFF", "valign": "vcenter"})
                fmt_money = wb.add_format({"num_format": "$#,##0.00", "border": 1})
                fmt_money_even = wb.add_format({"num_format": "$#,##0.00", "border": 1, "bg_color": "#F8FAFF"})
                fmt_total = wb.add_format({
                    "bold": True, "num_format": "$#,##0.00",
                    "bg_color": "#0F3460", "font_color": "white", "border": 1,
                })
                fmt_total_lbl = wb.add_format({
                    "bold": True, "bg_color": "#0F3460", "font_color": "white", "border": 1,
                })
                fmt_puc_code = wb.add_format({
                    "border": 1, "font_color": "#075985", "bg_color": "#E0F2FE",
                    "bold": True, "font_name": "Courier New", "font_size": 9,
                })
                fmt_puc_empty = wb.add_format({
                    "border": 1, "font_color": "#94A3B8", "italic": True,
                })
                fmt_tipo_i = wb.add_format({"border": 1, "font_color": "#15803D", "bold": True})
                fmt_tipo_g = wb.add_format({"border": 1, "font_color": "#B91C1C", "bold": True})

                # ── HOJA: Movimientos ──────────────────────────────
                ws1_name = "Movimientos"
                if df_mov.empty:
                    pd.DataFrame([{"Mensaje": "No hay movimientos en el rango seleccionado."}]).to_excel(
                        writer, index=False, sheet_name=ws1_name
                    )
                else:
                    # Escribir manualmente con formato
                    ws1 = wb.add_worksheet(ws1_name)
                    writer.sheets[ws1_name] = ws1

                    cols = list(df_mov.columns)
                    puc_cols = {"Código PUC", "Nombre cuenta PUC"}
                    money_cols = {"Débito", "Crédito"}

                    # Título
                    ws1.merge_range(0, 0, 0, len(cols) - 1,
                        f"Libro Diario Contable — {institucion.nombre} | {fecha_inicio} al {fecha_fin}",
                        wb.add_format({"bold": True, "font_size": 12, "font_color": "#0F3460",
                                       "bg_color": "#E8EEF8", "border": 1, "align": "center"}))
                    ws1.set_row(0, 20)

                    # Cabeceras
                    for ci, col in enumerate(cols):
                        fmt = fmt_hdr_puc if col in puc_cols else fmt_hdr
                        ws1.write(1, ci, col, fmt)
                    ws1.set_row(1, 28)

                    # Filas
                    movimientos_list = df_mov.to_dict("records")
                    totales_deb = Decimal("0.00")
                    totales_cred = Decimal("0.00")
                    for ri, row in enumerate(movimientos_list):
                        is_even = ri % 2 == 0
                        for ci, col in enumerate(cols):
                            val = row[col]
                            if col == "Código PUC":
                                ws1.write(ri + 2, ci, val, fmt_puc_code if val else fmt_puc_empty)
                            elif col == "Nombre cuenta PUC":
                                ws1.write(ri + 2, ci, val, fmt_even if is_even else fmt_cell)
                            elif col in money_cols:
                                num_val = float(val) if val else 0.0
                                ws1.write(ri + 2, ci, num_val,
                                          fmt_money_even if is_even else fmt_money)
                                if col == "Débito":  totales_deb  += Decimal(str(val or 0))
                                if col == "Crédito": totales_cred += Decimal(str(val or 0))
                            elif col == "Tipo":
                                fmt_t = fmt_tipo_i if str(val) == "Ingreso" else fmt_tipo_g
                                ws1.write(ri + 2, ci, val, fmt_t)
                            else:
                                ws1.write(ri + 2, ci, val,
                                          fmt_even if is_even else fmt_cell)

                    # Fila totales
                    tr = len(movimientos_list) + 2
                    ws1.write(tr, cols.index("Concepto") if "Concepto" in cols else 0,
                              "TOTALES", fmt_total_lbl)
                    if "Débito" in cols:
                        ws1.write(tr, cols.index("Débito"),  float(totales_deb),  fmt_total)
                    if "Crédito" in cols:
                        ws1.write(tr, cols.index("Crédito"), float(totales_cred), fmt_total)

                    # Anchos
                    ancho_col = {
                        "Fecha": 12, "Tipo": 10, "Código PUC": 12, "Nombre cuenta PUC": 32,
                        "Concepto": 32, "Documento tercero": 14, "Nombre tercero": 24,
                        "Método de pago": 18, "Referencia transacción": 22,
                        "N° recibo / documento": 14, "Observación": 28,
                        "Débito": 16, "Crédito": 16, "ID interno": 10,
                    }
                    for ci, col in enumerate(cols):
                        ws1.set_column(ci, ci, ancho_col.get(col, 14))
                    ws1.freeze_panes(2, 0)

                # ── HOJA: Resumen ──────────────────────────────────
                df_resumen.to_excel(writer, index=False, sheet_name="Resumen", startrow=1)
                ws0 = writer.sheets["Resumen"]
                ws0.merge_range("A1:B1", f"Resumen Exportación Contable — {institucion.nombre}",
                                wb.add_format({"bold": True, "font_size": 12, "font_color": "#0F3460",
                                               "bg_color": "#E8EEF8", "border": 1, "align": "center"}))
                ws0.write(1, 0, "Campo", fmt_hdr)
                ws0.write(1, 1, "Valor", fmt_hdr)
                for ri, (_, row) in enumerate(df_resumen.iterrows()):
                    ws0.write(ri + 2, 0, row["Campo"], fmt_cell)
                    ws0.write(ri + 2, 1, row["Valor"], fmt_cell)
                ws0.set_column(0, 0, 32)
                ws0.set_column(1, 1, 55)

            output.seek(0)
            response = HttpResponse(
                output.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{slug}.xlsx"'
            AuditoriaExportacionContable.objects.create(
                institucion=institucion,
                usuario=request.user,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                tipo_transaccion=tipo_transaccion,
                formato=formato,
                periodo_academico=periodo_sel,
                registros=len(movimientos),
            )
            return response
    else:
        form = ExportacionContableForm(inst=institucion)

    context = {
        "form": form,
        "titulo_pagina": "Exportación contable",
    }
    return render(request, "finanzas/exportacion_contable.html", context)


@login_required
def libro_diario_contable(request):
    """
    Consulta en pantalla del libro diario (mismos criterios que la exportación contable).
    """
    if not _puede_exportacion_contable(request.user):
        messages.error(
            request,
            "No tiene permisos para consultar el libro diario contable.",
        )
        return redirect("finanzas:reportes_exportaciones")

    institucion = getattr(request.user, "institucion_asociada", None)
    if not institucion:
        messages.error(
            request,
            "Debe tener una institución asociada para consultar el libro diario.",
        )
        return redirect("finanzas:reportes_exportaciones")

    today = date.today()
    default_initial = {
        "fecha_inicio": today.replace(day=1),
        "fecha_fin": today,
        "tipo_transaccion": "TODOS",
    }

    page_obj = None
    total_cred = Decimal("0.00")
    total_deb = Decimal("0.00")
    registros_total = 0
    filtros_qs = ""

    if request.GET:
        form = LibroDiarioContableForm(request.GET, inst=institucion)
        if form.is_valid():
            fecha_inicio = form.cleaned_data["fecha_inicio"]
            fecha_fin = form.cleaned_data["fecha_fin"]
            tipo_transaccion = form.cleaned_data["tipo_transaccion"]
            periodo_sel = form.cleaned_data.get("periodo_academico")
            movimientos = _movimientos_contables_rango(
                institucion, fecha_inicio, fecha_fin, tipo_transaccion, periodo_sel,
            )
            registros_total = len(movimientos)
            total_cred = sum((m["Crédito"] for m in movimientos), Decimal("0.00"))
            total_deb  = sum((m["Débito"]  for m in movimientos), Decimal("0.00"))
            filas = [_movimiento_fila_libro_tabla(m) for m in movimientos]
            filtros_qs = request.GET.urlencode()
    else:
        form = LibroDiarioContableForm(initial=default_initial, inst=institucion)
        movimientos = _movimientos_contables_rango(
            institucion,
            default_initial["fecha_inicio"],
            default_initial["fecha_fin"],
            default_initial["tipo_transaccion"],
            None,
        )
        registros_total = len(movimientos)
        total_cred = sum((m["Crédito"] for m in movimientos), Decimal("0.00"))
        total_deb  = sum((m["Débito"]  for m in movimientos), Decimal("0.00"))
        filas = [_movimiento_fila_libro_tabla(m) for m in movimientos]
        filtros_qs = ""

    # ── Agrupar por mes → día para el acordeón ──────────────────
    from collections import OrderedDict
    MESES_ES = {
        1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
        7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre",
    }
    grupos_dict = OrderedDict()
    for fila in filas:
        f = fila["fecha"]
        mes_key = (f.year, f.month)
        dia_key = f
        if mes_key not in grupos_dict:
            grupos_dict[mes_key] = {
                "label": f"{MESES_ES[f.month]} {f.year}",
                "key":   f"{f.year}-{f.month:02d}",
                "count": 0,
                "total_deb": Decimal("0.00"),
                "total_cred": Decimal("0.00"),
                "dias": OrderedDict(),
            }
        gm = grupos_dict[mes_key]
        gm["count"] += 1
        gm["total_deb"]  += fila["debito"]  or Decimal("0.00")
        gm["total_cred"] += fila["credito"] or Decimal("0.00")
        if dia_key not in gm["dias"]:
            gm["dias"][dia_key] = {
                "label": f.strftime("%d %b %Y"),
                "key":   f.strftime("%Y-%m-%d"),
                "count": 0,
                "total_deb":  Decimal("0.00"),
                "total_cred": Decimal("0.00"),
                "filas": [],
            }
        gd = gm["dias"][dia_key]
        gd["count"] += 1
        gd["total_deb"]  += fila["debito"]  or Decimal("0.00")
        gd["total_cred"] += fila["credito"] or Decimal("0.00")
        gd["filas"].append(fila)

    # Convertir a listas para el template
    grupos = []
    for gm in grupos_dict.values():
        gm["dias"] = list(gm["dias"].values())
        grupos.append(gm)

    return render(
        request,
        "finanzas/libro_diario_contable.html",
        {
            "titulo_pagina": "Libro diario contable",
            "form": form,
            "grupos": grupos,
            "total_cred": total_cred,
            "total_deb":  total_deb,
            "registros_total": registros_total,
            "filtros_qs": filtros_qs,
        },
    )


@login_required
def libro_diario_pdf(request):
    """Genera el PDF completo del libro diario con PUC, terceros y movimientos."""
    if not _puede_exportacion_contable(request.user):
        messages.error(request, "No tiene permisos para exportar el libro diario.")
        return redirect("finanzas:libro_diario_contable")

    institucion = getattr(request.user, "institucion_asociada", None)
    if not institucion:
        messages.error(request, "Debe tener una institución asociada.")
        return redirect("finanzas:libro_diario_contable")

    today = date.today()
    fecha_inicio_str = request.GET.get("fecha_inicio", today.replace(day=1).isoformat())
    fecha_fin_str = request.GET.get("fecha_fin", today.isoformat())
    tipo_transaccion = request.GET.get("tipo_transaccion", "TODOS")

    try:
        fecha_inicio = date.fromisoformat(fecha_inicio_str)
        fecha_fin = date.fromisoformat(fecha_fin_str)
    except ValueError:
        fecha_inicio = today.replace(day=1)
        fecha_fin = today

    movimientos = _movimientos_contables_rango(
        institucion, fecha_inicio, fecha_fin, tipo_transaccion, None
    )
    filas = [_movimiento_fila_libro_tabla(m) for m in movimientos]
    total_cred = sum((m["Crédito"] for m in movimientos), Decimal("0.00"))
    total_deb = sum((m["Débito"] for m in movimientos), Decimal("0.00"))

    context = {
        "institucion": institucion,
        "filas": filas,
        "total_cred": total_cred,
        "total_deb": total_deb,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "tipo_transaccion": tipo_transaccion,
        "generado_por": request.user.get_full_name() or request.user.get_username(),
    }
    template = get_template("finanzas/pdfs/libro_diario_contable.html")
    html = template.render(context)
    response = HttpResponse(content_type="application/pdf")
    pdf_name = f"LibroDiario_{fecha_inicio}_{fecha_fin}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{pdf_name}"'
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        logger.error("Error PDF libro diario: %s", pisa_status.err)
        return HttpResponse("Error al generar el PDF.", status=500)
    return response


def link_callback(uri, rel):  # noqa: F811
    """Segunda definición consolidada — protegida contra path traversal."""
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
        allowed_root = os.path.realpath(settings.MEDIA_ROOT)
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ''))
        allowed_root = os.path.realpath(settings.STATIC_ROOT)
    else:
        return uri
    real_path = os.path.realpath(path)
    if not real_path.startswith(allowed_root + os.sep) and real_path != allowed_root:
        logger.warning("link_callback: path traversal bloqueado para URI: %s", uri)
        return None
    if not os.path.isfile(real_path):
        return None
    return real_path

@login_required
def generar_factura_venta(request, cuenta_id):
    if request.user.is_superuser:
        cuenta = get_object_or_404(CuentaPorCobrarEstudiante, pk=cuenta_id)
    else:
        cuenta = get_object_or_404(
            CuentaPorCobrarEstudiante,
            pk=cuenta_id,
            institucion=request.user.institucion_asociada
        )

    # --- INICIO DE LA MEJORA ---
    # Buscamos todos los pagos que se han registrado para esta cuenta por cobrar.
    pagos_realizados = cuenta.pagos.all().order_by('fecha_pago')
    # --- FIN DE LA MEJORA ---

    context = {
        'cuenta': cuenta,
        'institucion': cuenta.institucion,
        'copias': ['Original', 'Copia'],
        'items': [], # Este campo parece no usarse, lo mantenemos por compatibilidad
        'pagos_realizados': pagos_realizados, # Pasamos los pagos a la plantilla
    }
    
    template = get_template('finanzas/pdfs/factura_venta.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="factura_venta_{cuenta.pk}.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        logger.error("Error al generar PDF factura venta (pisa.err=%s)", pisa_status.err)
        return HttpResponse('Error al generar el PDF. Por favor, inténtelo de nuevo.', status=500)
    
    return response

@login_required
def generar_comprobante_egreso(request, gasto_id):
    """
    Genera un Comprobante de Egreso (o Recibo de Caja Menor) en PDF para un Gasto.
    """
    if request.user.is_superuser:
        gasto = get_object_or_404(Gasto, pk=gasto_id)
    else:
        gasto = get_object_or_404(Gasto, pk=gasto_id, institucion=request.user.institucion_asociada)

    context = {
        'gasto': gasto,
        'institucion': gasto.institucion,
    }
    template = get_template('finanzas/pdfs/comprobante_egreso.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="comprobante_egreso_{gasto.pk}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF.', status=500)
    return response

@login_required
@permission_required('finanzas.add_cuentacontable', raise_exception=True)
@require_POST
def ejecutar_seed_puc_view(request):
    """
    Carga un Plan Único de Cuentas (PUC) básico para la institución del usuario.
    """
    try:
        # Intentamos obtener la institución del usuario
        institucion = getattr(request.user, 'institucion_asociada', None)

        # Si no hay institución asociada y es superusuario, buscamos la primera disponible (útil para pruebas/setup)
        if not institucion and request.user.is_superuser:
            institucion = InstitucionEducativa.objects.first()

        if not institucion:
            messages.error(request, "No se encontró una institución válida para cargar el PUC.")
            return redirect('finanzas:dashboard_financiero')

        # Definimos las cuentas base directamente aquí para evitar problemas con el comando seed_puc
        cuentas_base = [
            {'codigo': '1105', 'nombre': 'Caja', 'tipo': 'ACTIVO'},
            {'codigo': '1110', 'nombre': 'Bancos', 'tipo': 'ACTIVO'},
            {'codigo': '1305', 'nombre': 'Clientes', 'tipo': 'ACTIVO'},
            {'codigo': '2205', 'nombre': 'Proveedores Nacionales', 'tipo': 'PASIVO'},
            {'codigo': '2335', 'nombre': 'Costos y Gastos por Pagar', 'tipo': 'PASIVO'},
            {'codigo': '3105', 'nombre': 'Capital Suscrito y Pagado', 'tipo': 'PATRIMONIO'},
            {'codigo': '4140', 'nombre': 'Ingresos por Pensiones', 'tipo': 'INGRESO'},
            {'codigo': '4145', 'nombre': 'Ingresos por Matrículas', 'tipo': 'INGRESO'},
            {'codigo': '4295', 'nombre': 'Otros Ingresos', 'tipo': 'INGRESO'},
            {'codigo': '5105', 'nombre': 'Gastos de Personal', 'tipo': 'GASTO'},
            {'codigo': '5110', 'nombre': 'Honorarios', 'tipo': 'GASTO'},
            {'codigo': '5120', 'nombre': 'Arrendamientos', 'tipo': 'GASTO'},
            {'codigo': '5135', 'nombre': 'Servicios', 'tipo': 'GASTO'},
            {'codigo': '5145', 'nombre': 'Mantenimiento y Reparaciones', 'tipo': 'GASTO'},
            {'codigo': '5195', 'nombre': 'Diversos', 'tipo': 'GASTO'},
        ]

        creadas = 0
        for cuenta in cuentas_base:
            _, created = CuentaContable.objects.get_or_create(
                codigo=cuenta['codigo'],
                institucion=institucion,
                defaults={
                    'nombre': cuenta['nombre'],
                    'tipo': cuenta['tipo']
                }
            )
            if created:
                creadas += 1

        messages.success(request, f"¡Éxito! Se han verificado/creado {creadas} cuentas del PUC para {institucion.nombre}.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error al intentar cargar el PUC: {e}")

    # Al terminar, redirige de vuelta al dashboard financiero
    return redirect('finanzas:dashboard_financiero')

class CuentaContableListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = CuentaContable
    template_name = 'finanzas/puc_lista.html'
    context_object_name = 'cuentas'
    permission_required = 'finanzas.view_cuentacontable'

    def get_queryset(self):
        return CuentaContable.objects.filter(institucion=self.request.user.institucion_asociada).order_by('codigo')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Plan Único de Cuentas (PUC)"
        return context

class CuentaContableCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CuentaContable
    form_class = CuentaContableForm
    template_name = 'finanzas/puc_formulario.html'
    permission_required = 'finanzas.add_cuentacontable'
    success_url = reverse_lazy('finanzas:lista_cuentas_contables')

    def form_valid(self, form):
        # ✅ Asigna la institución automáticamente al guardar
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Cuenta contable creada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Crear Nueva Cuenta Contable"
        return context

class CuentaContableUpdateView(LoginRequiredMixin, PermissionRequiredMixin, CuentaContableInstitucionMixin, UpdateView):
    model = CuentaContable
    form_class = CuentaContableForm
    template_name = 'finanzas/puc_formulario.html'
    permission_required = 'finanzas.change_cuentacontable'
    success_url = reverse_lazy('finanzas:lista_cuentas_contables')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['institucion'] = self.request.user.institucion_asociada
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Cuenta contable actualizada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Cuenta: {self.object.nombre}"
        return context

class CuentaContableDeleteView(LoginRequiredMixin, PermissionRequiredMixin, CuentaContableInstitucionMixin, DeleteView):
    model = CuentaContable
    template_name = 'finanzas/puc_confirmar_eliminar.html'
    permission_required = 'finanzas.delete_cuentacontable'
    success_url = reverse_lazy('finanzas:lista_cuentas_contables')

    def form_valid(self, form):
        messages.success(self.request, f"La cuenta '{self.object.nombre}' ha sido eliminada.")
        return super().form_valid(form)    

@login_required
def iniciar_pago(request, cuenta_pk):
    """
    Crea una preferencia de pago en Mercado Pago para un estudiante ya matriculado.
    Redirige de vuelta al dashboard del estudiante después del pago.
    """
    logger.info(f"Iniciando pago de estudiante para la cuenta: {cuenta_pk}")

    # Aislamiento multi-institución: la cuenta debe pertenecer a la institución del usuario
    institucion = getattr(request.user, 'institucion_asociada', None)

    # Buscamos la cuenta asegurándonos que pertenece al usuario logueado Y a su institución
    cuenta = get_object_or_404(
        CuentaPorCobrarEstudiante.objects.select_related('estudiante__institucion', 'concepto_pago'),
        pk=cuenta_pk,
        estudiante__usuario=request.user,
        institucion=institucion,   # aislamiento multi-institución
    )
    
    estudiante = cuenta.estudiante
    institucion = estudiante.institucion

    try:
        access_token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test
        if not access_token:
            raise ValueError("Las credenciales de Mercado Pago no están configuradas para esta institución.")

        # --- LÓGICA DE RETORNO CORREGIDA ---
        # El destino final después de procesar el pago es el dashboard del estudiante.
        final_destination_url = reverse('gestion_academica:dashboard_estudiante')

        # Pasamos este destino a la página de procesamiento a través de un parámetro 'next'.
        query_params = {
            'cuenta_id': cuenta.id,
            'next': final_destination_url 
        }
        
        # Reutilizamos la página de procesamiento y el webhook de la app de admisiones
        base_procesando_url = request.build_absolute_uri(reverse('admisiones:pago_procesando'))
        url_procesando = f"{base_procesando_url}?{urlencode(query_params)}"
        notification_url = request.build_absolute_uri(reverse('admisiones:mercadopago_webhook')) + f"?institucion_id={institucion.id}"
        
        sdk = mercadopago.SDK(access_token)
        
        preference_data = {
            "items": [{"title": f"{cuenta.concepto_pago.nombre_concepto}", "quantity": 1, "unit_price": float(cuenta.saldo_pendiente), "currency_id": "COP"}],
            "payer": {"name": estudiante.usuario.first_name, "surname": estudiante.usuario.last_name, "email": estudiante.usuario.email},
            "back_urls": {"success": url_procesando, "failure": url_procesando, "pending": url_procesando},
            "auto_return": "approved",
            "notification_url": notification_url,
            "external_reference": str(cuenta.id),
        }
        
        logger.info("Enviando preferencia a MP (modo=%s) para estudiante: %s",
                    'PRODUCCIÓN' if institucion.mp_modo_produccion else 'TEST', preference_data)
        preference_response = sdk.preference().create(preference_data)

        if preference_response.get("status") >= 400:
            raise ValueError(f"Error de la API de Mercado Pago: {preference_response['response'].get('message', 'Error desconocido')}")

        # Seleccionar la URL correcta según el modo de la institución:
        # · Producción → init_point (checkout real)
        # · Test/Sandbox → sandbox_init_point (checkout de pruebas)
        resp = preference_response['response']
        if institucion.mp_modo_produccion:
            redirect_url = resp.get('init_point') or resp.get('sandbox_init_point')
        else:
            redirect_url = resp.get('sandbox_init_point') or resp.get('init_point')

        if not redirect_url:
            raise ValueError("La respuesta de Mercado Pago no contiene una URL de pago válida.")

        logger.info('Redirigiendo al checkout de MP (estudiante): %s', redirect_url)
        return redirect(redirect_url)
        
    except Exception as e:
        logger.error(f"Error al generar enlace de pago para cuenta {cuenta_pk}: {e}", exc_info=True)
        messages.error(request, f"Hubo un error al generar el enlace de pago: {e}")
        return redirect('finanzas:mi_estado_de_cuenta')
    

@require_POST # Esta vista solo aceptará peticiones POST para evitar ejecuciones accidentales
@login_required
@permission_required('finanzas.add_cuentaporcobrarestudiante', raise_exception=True)
def sincronizar_cuentas_masivo(request):
    """
    Sincroniza las cuentas automáticas de TODOS los estudiantes activos de la institución.
    """
    institucion_usuario = getattr(request.user, 'institucion_asociada', None)
    if not institucion_usuario and not request.user.is_superuser:
        messages.error(request, "Tu usuario no tiene una institución asociada.")
        return redirect('gestion_academica:inicio_academico')

    # Filtramos los estudiantes por la institución del usuario, a menos que sea superadmin
    if request.user.is_superuser:
        estudiantes_a_sincronizar = Estudiante.objects.filter(activo=True)
    else:
        estudiantes_a_sincronizar = Estudiante.objects.filter(activo=True, institucion=institucion_usuario)

    total_cuentas_creadas = 0
    total_estudiantes_procesados = 0
    total_advertencias = 0

    for estudiante in estudiantes_a_sincronizar:
        try:
            resultado = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)
            total_cuentas_creadas += resultado.total_cuentas_creadas
            if resultado.es_warning:
                total_advertencias += 1
                messages.warning(request, f"⚠ {estudiante}: {resultado.mensaje}")
            total_estudiantes_procesados += 1
        except Exception as e:
            messages.warning(request, f"Ocurrió un error procesando a {estudiante}: {e}")

    if total_cuentas_creadas > 0:
        messages.success(
            request,
            f"Sincronización masiva completada: {total_cuentas_creadas} nuevas cuentas "
            f"para {total_estudiantes_procesados} estudiantes "
            f"({total_advertencias} con advertencias).",
        )
    else:
        messages.info(request, "Sincronización masiva completada. No se encontraron nuevas cuentas para crear.")
    
    # Redirigimos de vuelta a la página del reporte general
    return redirect('finanzas:reporte_general_cuentas') # Asegúrate de que este sea el nombre correcto de tu reporte       


@login_required
def seleccionar_estudiante_para_historial(request):
    """
    Muestra una lista con buscador de todos los estudiantes de la institución
    para que el administrador pueda seleccionar uno y ver su historial de cuentas.
    """
    institucion = request.user.institucion_asociada
    
    query = request.GET.get('q', '')
    if query:
        estudiantes = Estudiante.objects.filter(
            Q(usuario__first_name__icontains=query) | 
            Q(usuario__last_name__icontains=query) | 
            Q(documento_identidad__icontains=query),
            institucion=institucion
        ).select_related('usuario', 'grado_actual')
    else:
        estudiantes = Estudiante.objects.filter(institucion=institucion).select_related('usuario', 'grado_actual')

    context = {
        'titulo_pagina': "Seleccionar Estudiante para Ver Cartera",
        'estudiantes': estudiantes,
        'query': query
    }
    return render(request, 'finanzas/seleccionar_estudiante_historial.html', context)    


