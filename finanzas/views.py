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
from django.http import HttpResponse
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
    CategoriaGasto, 
    Proveedor, 
    Gasto,  # <-- IMPORTACIÓN AÑADIDA
    Descuento,
    TipoGasto, # <-- AÑADE ESTA IMPORTACIÓN
    CategoriaGasto,
    CuentaContable
    
)

from gestion_academica.models import TicketSoporte, RespuestaTicket
from gestion_academica.forms import RespuestaTicketForm

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
    TipoGastoForm, # <-- AÑADE ESTA IMPORTACIÓN
    CategoriaGastoForm,
    CuentaContableForm,
    MasterPasswordForm
    
)

# Mixin para asegurar que todo sea multi-institución
class CuentaContableInstitucionMixin:
    def get_queryset(self):
        return CuentaContable.objects.filter(institucion=self.request.user.institucion_asociada)

from .mixins import InstitucionOwnedMixin

logger = logging.getLogger(__name__)


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

    return render(request, 'finanzas/configuracion_pagos.html', {'form': form, 'titulo_pagina': "Configuración de Pagos"})


@login_required
def dashboard_financiero(request):
    """
    Calcula y muestra los KPIs en el dashboard, con una consulta optimizada
    para la cartera vencida.
    """
    contexto_kpis = {}
    
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            today = date.today()
            primer_dia_mes = today.replace(day=1)

            # 1. Ingresos y Gastos del mes actual (Esto ya era eficiente)
            ingresos_mes = PagoRegistrado.objects.filter(
                institucion=institucion_usuario, 
                fecha_pago__gte=primer_dia_mes
            ).aggregate(total=Sum('valor_pagado'))['total'] or 0
            
            gastos_mes = Gasto.objects.filter(
                institucion=institucion_usuario, 
                fecha_gasto__gte=primer_dia_mes
            ).aggregate(total=Sum('monto'))['total'] or 0
            
            # 2. CÁLCULO OPTIMIZADO de Cartera Vencida
            cuentas_vencidas = CuentaPorCobrarEstudiante.objects.filter(
                institucion=institucion_usuario,
                estado='VENCIDO' # Solo traemos las que ya están marcadas como vencidas
            ).annotate(
                # Calculamos el saldo pendiente para cada una
                total_pagado=Coalesce(Sum('pagos__valor_pagado'), Decimal('0.0'))
            ).annotate(
                saldo=F('monto_asignado') - F('total_pagado')
            )
            
            # Sumamos los saldos calculados
            cartera_vencida = sum(c.saldo for c in cuentas_vencidas if c.saldo > 0)

            contexto_kpis = {
                'ingresos_mes': ingresos_mes,
                'gastos_mes': gastos_mes,
                'utilidad_mes': ingresos_mes - gastos_mes,
                'cartera_vencida': cartera_vencida,
            }

    context = {
        'titulo_pagina': 'Dashboard Financiero',
        'kpis': contexto_kpis
    }
    return render(request, 'finanzas/dashboard_financiero.html', context)


@login_required
def vista_financiera_dashboard(request):
    institucion_usuario = getattr(request.user, 'institucion_asociada', None)
    if request.user.is_superuser:
        queryset = Estudiante.objects.select_related('usuario', 'grado_actual').order_by('usuario__last_name')
    elif institucion_usuario:
        queryset = Estudiante.objects.filter(institucion=institucion_usuario).select_related('usuario', 'grado_actual').order_by('usuario__last_name')
    else:
        queryset = Estudiante.objects.none()
    return render(request, 'finanzas/listado_estudiantes.html', {'estudiantes': queryset, 'titulo_pagina': 'Cuentas por Estudiante'})


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

            # --- INICIO DE LA LÓGICA DE SINCRONIZACIÓN CON ADMISIONES ---
            try:
                concepto_pagado = pago.cuenta.concepto_pago
                aspirante = pago.cuenta.aspirante or (pago.estudiante and pago.estudiante.aspirante_origen)

                # Si el pago es de matrícula y el aspirante está esperando ser matriculado
                if aspirante and concepto_pagado.es_pago_matricula and aspirante.estado == 'APROBADO_MATRICULA':
                    aspirante.matricular()
                    messages.info(request, f"El estado del aspirante '{aspirante}' ha sido actualizado a 'Matriculado'.")
                
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

    context = {
        'form': form,
        'cuenta': cuenta,
        'titulo_pagina': "Registrar Nuevo Pago",
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
                        email = EmailMessage(asunto, cuerpo_html, f'"{pago.institucion.nombre}" <noreply@tudominio.com>', [email_destinatario])
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


def historial_cuentas_estudiante(request, estudiante_id):
    if request.user.is_superuser:
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id)
    else:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        estudiante = get_object_or_404(Estudiante, pk=estudiante_id, institucion=institucion_usuario)
    
    cuentas = CuentaPorCobrarEstudiante.objects.filter(estudiante=estudiante).order_by('-fecha_vencimiento_especifica')

    # ▼▼▼ LÍNEA CORREGIDA ▼▼▼
    context = {
        'estudiante': estudiante,
        'historial': cuentas  # Cambiamos 'cuentas' por 'historial' para que coincida con la plantilla
    }
    # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲
    
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
        # --- CAMBIO IMPORTANTE AQUÍ ---
        # Llamamos a la nueva función del Manager que es más inteligente
        cuentas_creadas = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)
        # --- FIN DEL CAMBIO ---
        
        if cuentas_creadas > 0:
            messages.success(request, f"Sincronización completa. Se crearon o verificaron {cuentas_creadas} cuenta(s) para {estudiante.usuario.get_full_name()}.")
        else:
            messages.info(request, f"El estado de cuenta de {estudiante.usuario.get_full_name()} ya está completo y sincronizado.")
            
    except Exception as e:
        messages.error(request, f"Ocurrió un error durante la sincronización: {e}")

    return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=estudiante.pk)

@login_required
def mi_estado_de_cuenta(request):
    estudiante = get_object_or_404(Estudiante, usuario=request.user)
    
    # Obtenemos todas las cuentas, las pendientes primero
    cuentas = estudiante.cuentas_por_cobrar.all().order_by('estado', 'fecha_vencimiento_especifica')
    
    context = {
        'estudiante': estudiante,
        'cuentas': cuentas,
        'hoy': timezone.now().date(), # <-- AÑADIMOS LA FECHA DE HOY
        'titulo_pagina': "Mi Estado de Cuenta"
    }
    return render(request, 'finanzas/mi_estado_de_cuenta.html', context)


# --- FLUJO DE MERCADO PAGO ---

@login_required
def iniciar_pago_mercadopago(request, cuenta_pk):
    from finanzas.models import CuentaPorCobrarEstudiante  # Ajusta si ya lo importaste antes

    cuenta = get_object_or_404(CuentaPorCobrarEstudiante, pk=cuenta_pk, estudiante=request.user.estudiante)

    if cuenta.saldo_pendiente <= 0:
        messages.info(request, "Esta cuenta ya ha sido pagada.")
        return redirect('finanzas:mi_estado_de_cuenta')

    institucion = cuenta.institucion
    access_token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test

    if not access_token:
        messages.error(request, "La pasarela de pagos no está configurada para esta institución.")
        return redirect('finanzas:mi_estado_de_cuenta')

    sdk = mercadopago.SDK(access_token)

    # ✅ URLs seguras con HTTPS dinámicas (funciona con ngrok)
    success_url = request.build_absolute_uri(reverse('finanzas:pago_respuesta_mp')).replace('http://', 'https://')
    notification_url = request.build_absolute_uri(reverse('finanzas:finanzas_mercadopago_webhook')).replace('http://', 'https://')

    preference_data = {
        "items": [{
            "title": f"Pago: {cuenta.concepto_pago.nombre_concepto}",
            "quantity": 1,
            "unit_price": float(cuenta.saldo_pendiente),
            "currency_id": "COP"
        }],
        "payer": {
            "email": cuenta.estudiante.usuario.email
        },
        "back_urls": {
            "success": success_url,
            "failure": success_url,
            "pending": success_url
        },
        "auto_return": "approved",
        "external_reference": f"CUENTA-{cuenta.pk}-{institucion.pk}",
        "notification_url": notification_url,
    }

    try:
        # 🚨 Log de preferencia enviada (útil para depuración)
        logger.info("Preferencia enviada a MP:\n%s", preference_data)

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {})

        url_pago = preference.get('init_point') or preference.get('sandbox_init_point')

        if not url_pago:
            logger.error("Mercado Pago no devolvió una URL de pago. Respuesta: %s", preference)
            raise KeyError("No se encontró 'init_point' ni 'sandbox_init_point' en la respuesta de Mercado Pago.")

        cuenta.mercadopago_preference_id = preference.get('id')
        cuenta.save(update_fields=['mercadopago_preference_id'])

        return redirect(url_pago)

    except Exception as e:
        logger.error(f"Error creando preferencia de MP: {e}", exc_info=True)
        messages.error(request, "Hubo un error al comunicarse con la pasarela de pagos.")
        return redirect('finanzas:mi_estado_de_cuenta')

@login_required
def pago_respuesta_mp(request):
    status = request.GET.get('status')
    if status == 'approved':
        messages.success(request, "¡Tu pago ha sido aprobado! Verás el cambio reflejado en tu estado de cuenta.")
    elif status == 'in_process' or status == 'pending':
        messages.info(request, "Tu pago está pendiente de confirmación.")
    elif status == 'rejected':
        messages.error(request, "Tu pago fue rechazado. Por favor, intenta de nuevo.")
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
            
            if not external_ref or not external_ref.startswith('CUENTA-'):
                logger.warning(f"Webhook Finanzas: Referencia externa no válida en pago {payment_id}: {external_ref}")
                return HttpResponse(status=200)

            _, cuenta_id_str, institucion_id_str = external_ref.split('-')
            
            cuenta = CuentaPorCobrarEstudiante.objects.select_for_update().get(
                pk=int(cuenta_id_str), 
                institucion__pk=int(institucion_id_str)
            )

            if not PagoRegistrado.objects.filter(referencia_transaccion=str(payment_id)).exists():
                PagoRegistrado.objects.create(
                    cuenta=cuenta,
                    estudiante=cuenta.estudiante,
                    valor_pagado=Decimal(payment_info['transaction_amount']),
                    metodo_pago='MERCADO_PAGO',
                    referencia_transaccion=str(payment_id),
                    institucion=institucion_del_pago
                )
                logger.info(f"Webhook de FINANZAS procesó pago para cuenta #{cuenta.id}")

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

# Necesitas esta función de ayuda para que xhtml2pdf encuentre imágenes y CSS
def link_callback(uri, rel):
    """
    Convierte los URI de HTML a rutas del sistema de archivos para que pisa
    pueda encontrar los recursos (imágenes, CSS, etc.).
    """
    # El código de esta función depende de cómo tengas configurados tus archivos estáticos.
    # Esta es una implementación común.
    import os
    from django.conf import settings
    
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
    else:
        return uri
    
    if not os.path.isfile(path):
        return None
    return path

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

    # Contexto para la plantilla del PDF
    context = {
        'pago': pago,
        'institucion': pago.institucion,
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
    
    context = {
        'estudiante': estudiante,
        'cuentas': [cuenta], # La plantilla puede iterar sobre una lista de un solo elemento
        'institucion': estudiante.institucion,
        'total_a_pagar': cuenta.saldo_pendiente,
        'tipo_volante': f"Volante de Pago - {cuenta.concepto_pago.nombre_concepto}",
    }

    template = get_template('finanzas/volante_pago.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="volante_{cuenta.pk}.pdf"'

    # Usamos la función link_callback que ya definimos para las imágenes
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)

    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF del volante.', status=500)
    
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

    # Aplicar filtros a la lista de estudiantes
    if grado_filter:
        estudiantes_qs = estudiantes_qs.filter(grado_actual__pk=grado_filter)
    if estudiante_filter:
        estudiantes_qs = estudiantes_qs.filter(pk=estudiante_filter)
    if estado_filter:
        estudiantes_qs = estudiantes_qs.filter(cuentas_por_cobrar__estado=estado_filter).distinct()
    
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
        'titulo_pagina': 'Reporte General por Grados'
    }
    return render(request, 'finanzas/estado_pagos.html', context)

# --- CRUD PARA CONCEPTO DE PAGO ---

class ConceptoPagoListView(LoginRequiredMixin, PermissionRequiredMixin, InstitucionOwnedMixin, ListView):
    model = ConceptoPago
    template_name = 'finanzas/listado_configuracion.html' # <-- CORREGIDO
    context_object_name = 'objetos'
    permission_required = 'finanzas.view_conceptopago'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('tipo_concepto', 'periodo_academico_aplicable').order_by('nombre_concepto')
    
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
    Exporta el historial de cuentas por cobrar a un archivo Excel,
    aplicando los mismos filtros que la vista de reporte general.
    """
    # Queryset base
    cuentas_qs = CuentaPorCobrarEstudiante.objects.select_related(
        'estudiante__usuario', 'estudiante__grado_actual', 'concepto_pago', 'institucion'
    )

    # Filtrado de seguridad por institución
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            cuentas_qs = cuentas_qs.filter(institucion=institucion_usuario)
        else:
            cuentas_qs = CuentaPorCobrarEstudiante.objects.none()

    # Aplicar los filtros que vienen en la URL
    grado_filter = request.GET.get('grado')
    estudiante_id_filter = request.GET.get('estudiante')
    estado_filter = request.GET.get('estado')

    if grado_filter:
        cuentas_qs = cuentas_qs.filter(estudiante__grado_actual__pk=grado_filter)
    if estudiante_id_filter:
        cuentas_qs = cuentas_qs.filter(estudiante__pk=estudiante_id_filter)
    if estado_filter:
        cuentas_qs = cuentas_qs.filter(estado=estado_filter)

    # Preparar los datos para el archivo Excel
    data = []
    for cuenta in cuentas_qs.order_by('estudiante__usuario__last_name', 'fecha_vencimiento_especifica'):
        data.append({
            'Estudiante': cuenta.estudiante.usuario.get_full_name(),
            'Grado': cuenta.estudiante.grado_actual.nombre if cuenta.estudiante.grado_actual else 'N/A',
            'Concepto': cuenta.concepto_pago.nombre_concepto,
            'Monto Asignado': cuenta.monto_asignado,
            'Monto Pagado': cuenta.monto_pagado_actual,
            'Saldo Pendiente': cuenta.saldo_pendiente,
            'Fecha de Vencimiento': cuenta.fecha_vencimiento_especifica.strftime('%Y-%m-%d'),
            'Estado': cuenta.get_estado_display(),
            'Institución': cuenta.institucion.nombre,
        })

    # Crear la respuesta con el archivo Excel
    df = pd.DataFrame(data)
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="Reporte_Cuentas_por_Cobrar.xlsx"'
    
    df.to_excel(response, index=False)

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
        pagos_qs = pagos_qs.filter(institucion=institucion_usuario)
        gastos_qs = gastos_qs.filter(institucion=institucion_usuario)

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
    institucion = getattr(request.user, 'institucion_asociada', None)
    if not institucion:
        messages.error(request, "Tu usuario no está asociado a ninguna institución.")
        return redirect('finanzas:dashboard_financiero')

    if request.method == 'POST':
        # Pasamos el usuario al formulario para que sepa qué filtrar
        form = FacturacionMasivaForm(request.POST, user=request.user)
        if form.is_valid():
            concepto = form.cleaned_data['concepto_pago']
            grados = form.cleaned_data['grados']
            toda_la_institucion = form.cleaned_data['toda_la_institucion']
            fecha_vencimiento = form.cleaned_data['fecha_vencimiento']
            
            if toda_la_institucion:
                estudiantes_a_facturar = Estudiante.objects.filter(institucion=institucion, activo=True)
            else:
                estudiantes_a_facturar = Estudiante.objects.filter(institucion=institucion, grado_actual__in=grados, activo=True)

            creadas = 0
            existentes = 0
            for estudiante in estudiantes_a_facturar:
                monto_final, observaciones = aplicar_descuentos_a_cuenta(estudiante, concepto)
                
                _, created = CuentaPorCobrarEstudiante.objects.get_or_create(
                    estudiante=estudiante,
                    concepto_pago=concepto,
                    defaults={
                        'monto_asignado': monto_final,
                        'fecha_vencimiento_especifica': fecha_vencimiento,
                        'institucion': institucion,
                        'observaciones_internas': observaciones
                    }
                )
                if created:
                    creadas += 1
                else:
                    existentes += 1
            
            messages.success(request, f"Proceso completado: Se crearon {creadas} nuevas cuentas. {existentes} estudiantes ya tenían este cobro.")
            return redirect('finanzas:facturacion_masiva')
    else:
        # Pasamos el usuario al formulario para que sepa qué filtrar
        form = FacturacionMasivaForm(user=request.user)

    context = {
        'form': form,
        'titulo_pagina': 'Facturación Masiva'
    }
    return render(request, 'finanzas/facturacion_masiva.html', context)

@login_required
@user_passes_test(lambda u: u.is_superuser) # Solo superusuarios pueden acceder
def dashboard_superadmin(request):
    """
    Muestra el dashboard global con métricas y el estado de configuración de cada institución.
    VERSIÓN ACTUALIZADA: Incluye el conteo de tickets de soporte abiertos.
    """
    # --- INICIO DE LA MODIFICACIÓN (LA "CERRADURA") ---
    # Verificamos si la bandera de 'autenticado' existe en la sesión del usuario.
    if not request.session.get('superadmin_autenticado'):
        # Si no existe, lo enviamos a la página de la clave maestra.
        return redirect('finanzas:superadmin_login')
    # --- FIN DE LA MODIFICACIÓN ---


    # --- 1. KPIs Globales (tu lógica original) ---
    total_instituciones = InstitucionEducativa.objects.count()
    total_estudiantes = Estudiante.objects.count()
    total_ingresos = PagoRegistrado.objects.aggregate(total=Sum('valor_pagado'))['total'] or 0
    total_gastos = Gasto.objects.aggregate(total=Sum('monto'))['total'] or 0

    # --- 2. Datos para el Gráfico (tu lógica original) ---
    ingresos_por_institucion_data = InstitucionEducativa.objects.annotate(
        total_ingresos=Coalesce(Sum('pagoregistrado__valor_pagado'), 0, output_field=DecimalField())
    ).order_by('-total_ingresos')

    chart_labels = [i.nombre for i in ingresos_por_institucion_data]
    chart_data = [float(i.total_ingresos) for i in ingresos_por_institucion_data]

    # --- 3. Tabla de Estado de Configuración (tu lógica original) ---
    instituciones = InstitucionEducativa.objects.annotate(
        num_estudiantes=Count('estudiantes', distinct=True),
        test_keys_ok=Case(
            When(
                Q(mp_public_key_test__isnull=False, mp_public_key_test__gt='') &
                Q(mp_access_token_test__isnull=False, mp_access_token_test__gt=''),
                then=Value('OK')
            ),
            default=Value('Pendiente'),
            output_field=CharField()
        ),
        prod_keys_ok=Case(
            When(
                Q(mp_public_key_prod__isnull=False, mp_public_key_prod__gt='') &
                Q(mp_access_token_prod__isnull=False, mp_access_token_prod__gt=''),
                then=Value('OK')
            ),
            default=Value('Pendiente'),
            output_field=CharField()
        )
    ).order_by('nombre')
    
    # --- 4. LÓGICA AÑADIDA PARA TICKETS DE SOPORTE ---
    tickets_abiertos_count = TicketSoporte.objects.filter(
        Q(estado='ABIERTO') | Q(estado='EN_PROGRESO')
    ).count()
    # --- FIN DE LA LÓGICA AÑADIDA ---

    context = {
        'total_instituciones': total_instituciones,
        'total_estudiantes': total_estudiantes,
        'total_ingresos': total_ingresos,
        'total_gastos': total_gastos,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'instituciones': instituciones,
        'titulo_pagina': "Dashboard Super-Administrador",
        # --- Pasamos el nuevo conteo a la plantilla ---
        'tickets_abiertos_count': tickets_abiertos_count,
    }
    return render(request, 'finanzas/dashboard_superadmin.html', context)

@user_passes_test(lambda u: u.is_superuser)
def superadmin_tickets_view(request):
    """
    Muestra al superadministrador una lista de todos los tickets de soporte.
    """
    todos_los_tickets = TicketSoporte.objects.select_related(
        'usuario_reporta', 'institucion'
    ).order_by('estado', '-ultima_actualizacion')
    
    context = {
        'titulo_pagina': "Panel de Soporte (Superadmin)",
        'tickets': todos_los_tickets
    }
    # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
    return render(request, 'finanzas/superadmin_tickets.html', context)
    # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲


@user_passes_test(lambda u: u.is_superuser)
def superadmin_ticket_detail_view(request, ticket_id):
    """
    Muestra el detalle de un ticket y permite al superadministrador responder.
    """
    ticket = get_object_or_404(TicketSoporte, ticket_id=ticket_id)
    
    if request.method == 'POST':
        form = RespuestaTicketForm(request.POST, request.FILES)
        if form.is_valid():
            respuesta = form.save(commit=False)
            respuesta.ticket = ticket
            respuesta.autor = request.user
            respuesta.save()
            
            if ticket.estado == TicketSoporte.Estado.ABIERTO:
                ticket.estado = TicketSoporte.Estado.EN_PROGRESO
                ticket.save(update_fields=['estado', 'ultima_actualizacion'])
            
            messages.success(request, "Tu respuesta ha sido añadida al ticket.")
            return redirect('finanzas:superadmin_ticket_detail', ticket_id=ticket.ticket_id)
    else:
        form = RespuestaTicketForm()

    context = {
        'titulo_pagina': f"Detalle del Ticket [{ticket.ticket_id}]",
        'ticket': ticket,
        'respuestas': ticket.respuestas.select_related('autor').order_by('fecha_creacion'),
        'form': form
    }
    # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
    return render(request, 'finanzas/superadmin_ticket_detail.html', context)
    # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲    


@require_POST # Esta vista solo acepta peticiones POST por seguridad
@user_passes_test(lambda u: u.is_superuser)
def toggle_institucion_activa(request, pk):
    """
    Activa o desactiva una institución. Es llamada por el interruptor
    en el dashboard de super-admin.
    """
    institucion = get_object_or_404(InstitucionEducativa, pk=pk)
    institucion.activa = not institucion.activa # Invierte el valor actual (True -> False, False -> True)
    institucion.save(update_fields=['activa'])
    
    estado = "activada" if institucion.activa else "desactivada"
    messages.success(request, f"La institución '{institucion.nombre}' ha sido {estado}.")
    
    return redirect('finanzas:dashboard_superadmin')
 

@login_required
@permission_required('finanzas.view_pagoregistrado')
def exportacion_contable(request):
    if request.method == 'POST':
        form = ExportacionContableForm(request.POST)
        if form.is_valid():
            fecha_inicio = form.cleaned_data['fecha_inicio']
            fecha_fin = form.cleaned_data['fecha_fin']
            tipo_transaccion = form.cleaned_data['tipo_transaccion']
            institucion = request.user.institucion_asociada
            
            movimientos = []

            if tipo_transaccion in ['TODOS', 'INGRESOS']:
                ingresos = PagoRegistrado.objects.filter(
                    institucion=institucion, fecha_pago__range=[fecha_inicio, fecha_fin]
                ).select_related('estudiante__usuario', 'cuenta__concepto_pago__cuenta_contable')
                
                for pago in ingresos:
                    cuenta_contable = pago.cuenta.concepto_pago.cuenta_contable
                    movimientos.append({
                        'Fecha': pago.fecha_pago, 'Tipo': 'Ingreso',
                        'Cuenta Contable': cuenta_contable.codigo if cuenta_contable else '',
                        'Tercero (NIT/CC)': pago.estudiante.documento_identidad or '',
                        'Nombre Tercero': pago.estudiante.usuario.get_full_name(),
                        'Concepto/Descripción': pago.cuenta.concepto_pago.nombre_concepto,
                        'Débito': 0, 'Crédito': pago.valor_pagado
                    })

            if tipo_transaccion in ['TODOS', 'GASTOS']:
                gastos = Gasto.objects.filter(
                    institucion=institucion, fecha_gasto__range=[fecha_inicio, fecha_fin]
                ).select_related('proveedor', 'categoria__cuenta_contable')

                for gasto in gastos:
                    cuenta_contable = gasto.categoria.cuenta_contable
                    movimientos.append({
                        'Fecha': gasto.fecha_gasto, 'Tipo': 'Gasto',
                        'Cuenta Contable': cuenta_contable.codigo if cuenta_contable else '',
                        'Tercero (NIT/CC)': gasto.proveedor.nit_o_cedula if gasto.proveedor else '',
                        'Nombre Tercero': gasto.proveedor.nombre if gasto.proveedor else 'Varios',
                        'Concepto/Descripción': gasto.descripcion,
                        'Débito': gasto.monto, 'Crédito': 0
                    })
            
            movimientos.sort(key=lambda x: x['Fecha'])
            df = pd.DataFrame(movimientos)
            if not df.empty:
                df = df[['Fecha', 'Tipo', 'Cuenta Contable', 'Tercero (NIT/CC)', 'Nombre Tercero', 'Concepto/Descripción', 'Débito', 'Crédito']]
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='ComprobanteContable')
                workbook = writer.book
                worksheet = writer.sheets['ComprobanteContable']
                money_format = workbook.add_format({'num_format': '$#,##0.00'})
                worksheet.set_column('G:H', 18, money_format)
                worksheet.set_column('A:F', 22)

            output.seek(0)
            response = HttpResponse(output.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename="Exportacion_Contable_{fecha_inicio}_a_{fecha_fin}.xlsx"'
            return response
    else:
        form = ExportacionContableForm()

    context = {'form': form, 'titulo_pagina': 'Exportación Contable'}
    return render(request, 'finanzas/exportacion_contable.html', context)

def link_callback(uri, rel):
    import os
    from django.conf import settings
    logger.info(f"Procesando URI: {uri}")
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ''))
    else:
        path = uri
    logger.info(f"Ruta calculada: {path}")
    if not os.path.isfile(path):
        logger.warning(f"Archivo no encontrado: {path}")
        return None
    return path

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
        logger.error(f"Error al generar PDF: {pisa_status.err}")
        return HttpResponse(f'Ocurrió un error al generar el PDF: {pisa_status.err}', status=500)
    
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

@permission_required('finanzas.add_cuentacontable', raise_exception=True) # O un permiso de superadmin
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
    
    # Buscamos la cuenta asegurándonos que pertenece al usuario logueado
    cuenta = get_object_or_404(
        CuentaPorCobrarEstudiante.objects.select_related('estudiante__institucion', 'concepto_pago'), 
        pk=cuenta_pk, 
        estudiante__usuario=request.user
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
        
        logger.info("Enviando preferencia a Mercado Pago para estudiante: %s", preference_data)
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response.get("status") >= 400:
            raise ValueError(f"Error de la API de Mercado Pago: {preference_response['response'].get('message', 'Error desconocido')}")
        
        redirect_url = preference_response['response'].get('sandbox_init_point') or preference_response['response'].get('init_point')
        if not redirect_url:
            raise ValueError("La respuesta de Mercado Pago no contiene una URL de pago válida.")
            
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
    
    for estudiante in estudiantes_a_sincronizar:
        try:
            # --- INICIO DE LA CORRECCIÓN ---
            # Llamamos a la función del Manager con su nombre nuevo y correcto.
            cuentas_creadas = CuentaPorCobrarEstudiante.objects.sincronizar_cuentas_automaticas(estudiante)
            # --- FIN DE LA CORRECCIÓN ---
            total_cuentas_creadas += cuentas_creadas
            total_estudiantes_procesados += 1
        except Exception as e:
            messages.warning(request, f"Ocurrió un error procesando a {estudiante}: {e}")

    if total_cuentas_creadas > 0:
        messages.success(request, f"Sincronización masiva completada: Se crearon {total_cuentas_creadas} nuevas cuentas para {total_estudiantes_procesados} estudiantes.")
    else:
        messages.info(request, "Sincronización masiva completada. No se encontraron nuevas cuentas para crear.")
    
    # Redirigimos de vuelta a la página del reporte general
    return redirect('finanzas:reporte_general_cuentas') # Asegúrate de que este sea el nombre correcto de tu reporte       


@user_passes_test(lambda u: u.is_superuser)
def superadmin_tickets_view(request):
    """
    Muestra al superadministrador una lista de todos los tickets de soporte
    de todas las instituciones.
    """
    todos_los_tickets = TicketSoporte.objects.select_related(
        'usuario_reporta', 'institucion'
    ).order_by('estado', '-ultima_actualizacion')
    
    context = {
        'titulo_pagina': "Panel de Soporte (Superadmin)",
        'tickets': todos_los_tickets
    }
    return render(request, 'finanzas/superadmin_tickets.html', context)


@user_passes_test(lambda u: u.is_superuser)
def superadmin_ticket_detail_view(request, ticket_id):
    """
    Muestra el detalle de un ticket y permite al superadministrador responder.
    """
    ticket = get_object_or_404(TicketSoporte, ticket_id=ticket_id)
    
    if request.method == 'POST':
        form = RespuestaTicketForm(request.POST, request.FILES)
        if form.is_valid():
            respuesta = form.save(commit=False)
            respuesta.ticket = ticket
            respuesta.autor = request.user
            respuesta.save()
            
            if ticket.estado == TicketSoporte.Estado.ABIERTO:
                ticket.estado = TicketSoporte.Estado.EN_PROGRESO
                ticket.save(update_fields=['estado', 'ultima_actualizacion'])
            
            messages.success(request, "Tu respuesta ha sido añadida al ticket.")
            return redirect('finanzas:superadmin_ticket_detail', ticket_id=ticket.ticket_id) # <-- CORREGIDO
    else:
        form = RespuestaTicketForm()

    context = {
        'titulo_pagina': f"Detalle del Ticket [{ticket.ticket_id}]",
        'ticket': ticket,
        'respuestas': ticket.respuestas.select_related('autor').order_by('fecha_creacion'),
        'form': form
    }
    return render(request, 'finanzas/superadmin_ticket_detail.html', context)

@require_POST # Esta vista solo se puede llamar con un método POST
@user_passes_test(lambda u: u.is_superuser)
def cerrar_ticket_view(request, ticket_id):
    """
    Cambia el estado de un ticket a 'Cerrado'.
    """
    ticket = get_object_or_404(TicketSoporte, ticket_id=ticket_id)
    
    # Cambiamos el estado y guardamos
    ticket.estado = TicketSoporte.Estado.CERRADO
    ticket.save(update_fields=['estado', 'ultima_actualizacion'])
    
    messages.success(request, f"El ticket [{ticket.ticket_id}] ha sido cerrado exitosamente.")
    
    # Redirigimos de vuelta a la página de detalle del ticket
    return redirect('finanzas:superadmin_ticket_detail', ticket_id=ticket.ticket_id)    

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


@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_login_view(request):
    """
    Muestra el formulario para introducir la clave maestra y la valida.
    """
    if request.method == 'POST':
        form = MasterPasswordForm(request.POST)
        if form.is_valid():
            entered_password = form.cleaned_data['master_password']
            master_password = getattr(settings, 'SUPERADMIN_MASTER_PASSWORD', None)

            if entered_password == master_password:
                # Si la clave es correcta, ponemos la "llave" en la sesión.
                request.session['superadmin_autenticado'] = True
                # Y lo enviamos al dashboard que ahora sí podrá ver.
                return redirect('finanzas:dashboard_superadmin')
            else:
                messages.error(request, "La clave maestra es incorrecta.")
        else:
            messages.error(request, "Por favor, introduce una clave.")
    else:
        form = MasterPasswordForm()

    return render(request, 'finanzas/superadmin_login.html', {'form': form})   

@login_required
@user_passes_test(lambda u: u.is_superuser)
def superadmin_lock_view(request):
    """
    Cierra la sesión de la clave maestra eliminando la bandera de la sesión,
    pero mantiene al usuario logueado en la plataforma.
    VERSIÓN CORREGIDA: Redirige al dashboard académico, no al login.
    """
    if 'superadmin_autenticado' in request.session:
        del request.session['superadmin_autenticado']
        messages.info(request, "El Dashboard Super-Administrador ha sido bloqueado.")
    
    
    return redirect('gestion_academica:inicio_academico')
