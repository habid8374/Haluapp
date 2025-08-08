# admisiones/views.py

# --- Importaciones (sin cambios) ---
import io
import pandas as pd
from openpyxl.styles import Font
import mercadopago
from django.conf import settings
from django.db.models import Sum
import json
from urllib.parse import urlencode
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.generic import DetailView, UpdateView, DeleteView
from django.db import models
from django.db.models import Count, Value, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.db import transaction
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import traceback
from django.http import Http404
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font
import time
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from .models import Aspirante, DocumentoRequerido, DocumentoEntregado, HorarioDisponible, CitaAgendada
from gestion_academica.models import Grado, Usuario, Estudiante
from .forms import AspiranteForm, ImportarAspirantesForm
from .utils import crear_cuenta_cobro_inscripcion, enviar_correo_bienvenida, enviar_correo_cambio_estado, enviar_correo_confirmacion_cita
from finanzas.models import CuentaPorCobrarEstudiante, PagoRegistrado, InstitucionEducativa, ConceptoPago
from datetime import timedelta
from gestion_academica.models import PeriodoAcademico



logger = logging.getLogger(__name__)


# --- 2. VISTAS PRINCIPALES DEL CRUD Y LÓGICA DE NEGOCIO ---

@login_required
@permission_required('admisiones.view_aspirante', raise_exception=True)
def listar_aspirantes(request):
    """ Muestra solo los aspirantes de la institución del usuario logueado. """
    aspirantes = Aspirante.objects.filter(
        institucion=request.user.institucion_asociada
    ).select_related('grado_aspira').order_by('-fecha_inscripcion')
    
    context = {'aspirantes': aspirantes, 'titulo_pagina': "Gestión de Aspirantes"}
    return render(request, 'admisiones/lista_aspirantes.html', context)

@login_required
@permission_required('admisiones.add_aspirante', raise_exception=True)
def crear_aspirante_manual(request):
    institucion_usuario = request.user.institucion_asociada

    if request.method == 'POST':
        form = AspiranteForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    aspirante = form.save(commit=False)
                    aspirante.institucion = institucion_usuario
                    aspirante.save()
                    aspirante.procesar_inscripcion_completa()
                
                messages.success(request, f"Aspirante '{aspirante.nombres} {aspirante.apellidos}' registrado exitosamente.")
                
                # ▼▼▼ CORRECCIÓN DE LA REDIRECCIÓN ▼▼▼
                # Apuntamos a la URL correcta que lista los grados con aspirantes.
                return redirect('admisiones:lista_grados_aspirantes')

            except Exception as e:
                # Este bloque ahora solo se activará si hay un error real en la creación.
                messages.error(request, f"Ocurrió un error al registrar al aspirante: {e}")
    else:
        form = AspiranteForm(user=request.user)

    context = {
        'form': form,
        'titulo_pagina': 'Registrar Nuevo Aspirante Manualmente'
    }
    return render(request, 'admisiones/formulario_aspirante_manual.html', context)

@login_required
@permission_required('admisiones.change_aspirante')
def admitir_aspirante(request, aspirante_id):
    aspirante = get_object_or_404(Aspirante, pk=aspirante_id)
    grado_aspirado = aspirante.grado_aspira
    nivel_escolaridad = getattr(grado_aspirado, 'nivel_escolaridad', None)

    if not nivel_escolaridad:
        messages.error(request, f"El grado '{grado_aspirado}' no tiene un Nivel de Escolaridad asignado.")
        return redirect('admisiones:detalle_aspirante', pk=aspirante.id)

    try:
        # ✅ BÚSQUEDA POR NOMBRE
        concepto_matricula = ConceptoPago.objects.get(
            institucion=aspirante.institucion,
            nombre_concepto__icontains='Matrícula',
            nivel_escolaridad=nivel_escolaridad
        )
    except (ConceptoPago.DoesNotExist, ConceptoPago.MultipleObjectsReturned):
        messages.error(request, f"Error: No se encontró (o hay duplicados) un Concepto de Pago con 'Matrícula' para el nivel '{nivel_escolaridad}'.")
        return redirect('admisiones:detalle_aspirante', pk=aspirante.id)

    with transaction.atomic():
        CuentaPorCobrarEstudiante.objects.get_or_create(
            aspirante=aspirante,
            concepto_pago=concepto_matricula,
            defaults={'monto_asignado': concepto_matricula.valor}
        )
        aspirante.estado = Aspirante.EstadoAdmision.ADMITIDO
        aspirante.save()

    messages.success(request, "Aspirante admitido y cobro de matrícula generado.")
    return redirect('admisiones:detalle_aspirante', pk=aspirante.id)

class AspiranteMultiInstitucionMixin:
    """ Mixin para filtrar querysets por la institución del usuario. """
    def get_queryset(self):
        return self.model.objects.filter(institucion=self.request.user.institucion_asociada)    

# --- Vistas Basadas en Clases (Completas) ---
class AspiranteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Aspirante
    template_name = 'admisiones/detalle_aspirante.html'
    context_object_name = 'aspirante'
    permission_required = 'admisiones.view_aspirante'

    def get_queryset(self):
        # Tu lógica de seguridad multi-institución está perfecta y se mantiene
        return Aspirante.objects.filter(institucion=self.request.user.institucion_asociada)

    def get_context_data(self, **kwargs):
        """
        Añade los cobros del aspirante al contexto para mostrarlos en la plantilla.
        """
        context = super().get_context_data(**kwargs)
        aspirante = self.get_object()
        
        # --- ✅ INICIO DE LA LÓGICA AÑADIDA ---
        # Buscamos en la nueva tabla todas las cuentas por cobrar
        # que pertenezcan a ESTE aspirante.
        context['cuentas_del_aspirante'] = CuentaPorCobrarEstudiante.objects.filter(
            aspirante=aspirante
        ).select_related('concepto_pago').order_by('-fecha_creacion')
        # --- FIN DE LA LÓGICA AÑADIDA ---
        
        context['titulo_pagina'] = f"Perfil del Aspirante: {aspirante}"
        return context

class AspiranteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Aspirante
    form_class = AspiranteForm
    template_name = 'admisiones/formulario_inscripcion.html'
    permission_required = 'admisiones.change_aspirante'
    # Asumo que tienes un Mixin para filtrar por institución, lo mantengo si existe
    # de lo contrario, puedes añadir el método get_queryset como en otras vistas.

    def get_success_url(self):
        """
        Define a dónde redirigir al usuario después de editar exitosamente.
        """
        messages.success(self.request, "La información del aspirante ha sido actualizada.")
        # --- CORRECCIÓN AQUÍ ---
        # Cambiamos 'lista_aspirantes' por la URL que sí existe.
        return reverse_lazy('admisiones:lista_grados_aspirantes')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Editar Aspirante: {self.object}"
        return context



class AspiranteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, AspiranteMultiInstitucionMixin, DeleteView):
    model = Aspirante
    template_name = 'admisiones/confirmar_eliminacion_aspirante.html'
    context_object_name = 'aspirante'
    permission_required = 'admisiones.delete_aspirante'

    def get_success_url(self):
        """
        Define a dónde redirigir al usuario después de eliminar exitosamente.
        """
        messages.success(self.request, f"El aspirante '{self.object}' ha sido eliminado.")
        # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
        # Cambiamos la URL de redirección a la que sí existe.
        return reverse_lazy('admisiones:lista_grados_aspirantes')
        # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Confirmar Eliminación"
        return context


def vista_agendamiento(request, token):
    aspirante = get_object_or_404(Aspirante, access_token=token)
    if aspirante.estado != 'ADMITIDO':
        messages.warning(request, "Aún no estás en la etapa de agendamiento de citas.")
        return redirect('admisiones:portal_postulante', token=token)
    if hasattr(aspirante, 'cita_agendada'):
        messages.info(request, "Ya tienes una cita agendada.")
        return redirect('admisiones:portal_postulante', token=token)
    horarios = HorarioDisponible.objects.filter(
    institucion=aspirante.institucion,
    fecha_hora_inicio__gte=timezone.now()
    ).annotate(citas_count=Count('citas_agendadas')).filter(citas_count__lt=models.F('cupos_disponibles'))
    context = {'aspirante': aspirante, 'horarios_disponibles': horarios, 'titulo_pagina': "Agendar Cita de Admisión"}
    return render(request, 'admisiones/agendar_cita.html', context)

# --- 4. VISTAS DE DASHBOARD, IMPORTACIÓN Y EXPORTACIÓN ---

@login_required
@permission_required('admisiones.view_aspirante', raise_exception=True)
def dashboard_admisiones(request):
    return render(request, 'admisiones/dashboard.html', {'titulo_pagina': 'Dashboard de Admisiones'})

@login_required
def dashboard_data(request):
    """ 
    Proporciona datos JSON para el dashboard, mostrando estadísticas de TODOS 
    los aspirantes del periodo académico activo, incluyendo los ya matriculados.
    """
    institucion_usuario = getattr(request.user, 'institucion_asociada', None)

    if not institucion_usuario:
        return JsonResponse({'error': 'El usuario actual no está asociado a ninguna institución.'}, status=400)

    # 1. Buscamos el periodo académico activo para definir el ciclo de admisión
    periodo_activo = PeriodoAcademico.objects.filter(
        institucion=institucion_usuario, 
        activo=True
    ).first()

    if not periodo_activo:
        return JsonResponse({'error': 'No hay un periodo académico activo configurado en el sistema.'}, status=404)

    # 2. El Queryset base ahora filtra por las fechas del periodo activo
    base_queryset = Aspirante.objects.filter(
        institucion=institucion_usuario,
        fecha_inscripcion__date__range=(periodo_activo.fecha_inicio, periodo_activo.fecha_fin)
    )

    # --- El resto de la lógica para agregar los datos se mantiene igual ---
    
    data_por_estado = base_queryset.values('estado').annotate(total=Count('id')).order_by()
    
    data_por_grado = base_queryset.annotate(
        grado_nombre=Coalesce('grado_aspira__nombre', Value('Sin Asignar'))
    ).values('grado_nombre').annotate(total=Count('id')).order_by('-total')
    
    data_por_colegio = base_queryset.exclude(colegio_procedencia__isnull=True).exclude(colegio_procedencia__exact='').values('colegio_procedencia').annotate(total=Count('id')).order_by('-total')[:10]
    
    data_por_municipio = base_queryset.exclude(municipio_ciudad__isnull=True).exclude(municipio_ciudad__exact='').values('municipio_ciudad').annotate(total=Count('id')).order_by('-total')[:10]
    
    sexo_display_map = dict(Aspirante._meta.get_field('sexo').choices)
    data_por_sexo_raw = base_queryset.values('sexo').annotate(total=Count('id')).order_by()
    data_por_sexo = [
        {'sexo_label': sexo_display_map.get(item['sexo'], 'No especificado'), 'total': item['total']}
        for item in data_por_sexo_raw
    ]

    response_data = {
        'porEstado': {'labels': [item['estado'] for item in data_por_estado], 'data': [item['total'] for item in data_por_estado]},
        'porGrado': {'labels': [item['grado_nombre'] for item in data_por_grado], 'data': [item['total'] for item in data_por_grado]},
        'porColegio': {'labels': [item['colegio_procedencia'] for item in data_por_colegio], 'data': [item['total'] for item in data_por_colegio]},
        'porMunicipio': {'labels': [item['municipio_ciudad'] for item in data_por_municipio], 'data': [item['total'] for item in data_por_municipio]},
        'porSexo': {'labels': [item['sexo_label'] for item in data_por_sexo], 'data': [item['total'] for item in data_por_sexo]}
    }
    return JsonResponse(response_data)

@login_required
@permission_required('admisiones.add_aspirante')
def descargar_plantilla_importacion(request):
    """
    Genera la plantilla de Excel DEFINITIVA con nombres de columna simples
    y una lista desplegable de grados para evitar errores.
    """
    institucion = request.user.institucion_asociada
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Aspirantes"
    
    headers = [
        'nombres', 'apellidos', 'numero_documento', 'fecha_nacimiento',
        'email_contacto', 'telefono_contacto', 'grado_aspira', 'sexo',
        'colegio_procedencia', 'municipio_ciudad', 'departamento', 'paga_inscripcion'
    ]
    ws.append(headers)

    grados = Grado.objects.filter(institucion=institucion).order_by('orden')
    if grados.exists():
        grado_names = f'"{",".join([grado.nombre for grado in grados])}"'
        dv_grado = DataValidation(type="list", formula1=grado_names, allow_blank=False)
        ws.add_data_validation(dv_grado)
        dv_grado.add('G2:G1000') # Columna G (grado_aspira)

    dv_sexo = DataValidation(type="list", formula1='"M,F,O"', allow_blank=True)
    ws.add_data_validation(dv_sexo)
    dv_sexo.add('H2:H1000')

    dv_paga = DataValidation(type="list", formula1='"SI,NO"', allow_blank=False)
    ws.add_data_validation(dv_paga)
    dv_paga.add('L2:L1000')

    bold_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold_font
    for col_cells in ws.columns:
        max_length = max(len(str(cell.value or '')) for cell in col_cells)
        ws.column_dimensions[col_cells[0].column_letter].width = max_length + 2

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="plantilla_importacion_aspirantes.xlsx"'
    wb.save(response)
    return response


@login_required
@permission_required('admisiones.add_aspirante', raise_exception=True)
def importar_aspirantes_excel(request):
    institucion_actual = request.user.institucion_asociada
    if request.method == 'POST':
        form = ImportarAspirantesForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo_excel']
            try:
                df = pd.read_excel(archivo, dtype=str, keep_default_na=False)
                df.columns = [str(col).strip().lower() for col in df.columns]
                
                aspirantes_creados_count = 0
                errores = []

                for index, row in df.iterrows():
                    try:
                        with transaction.atomic():
                            documento = str(row.get('numero_documento', '')).strip()
                            grado_nombre = str(row.get('grado_aspira', '')).strip()
                            fecha_str = row.get('fecha_nacimiento')

                            if not (documento and grado_nombre and fecha_str):
                                raise ValueError("Las columnas 'numero_documento', 'grado_aspira' y 'fecha_nacimiento' son obligatorias.")

                            if Aspirante.objects.filter(numero_documento=documento, institucion=institucion_actual).exists():
                                errores.append(f"Fila {index + 2}: El aspirante con documento '{documento}' ya existe.")
                                continue
                            
                            # ✅ BÚSQUEDA DEL GRADO POR NOMBRE, NO POR ID
                            grado = Grado.objects.select_related('nivel_escolaridad').get(
                                nombre__iexact=grado_nombre, 
                                institucion=institucion_actual
                            )
                            
                            aspirante = Aspirante.objects.create(
                                institucion=institucion_actual,
                                nombres=str(row.get('nombres', '')).strip(),
                                apellidos=str(row.get('apellidos', '')).strip(),
                                numero_documento=documento,
                                grado_aspira=grado,
                                fecha_nacimiento=pd.to_datetime(fecha_str, dayfirst=True).date(),
                                email_contacto=str(row.get('email_contacto', '')).strip(),
                                telefono_contacto=str(row.get('telefono_contacto', '')).strip(),
                                sexo=str(row.get('sexo', 'O')).strip().upper(),
                                colegio_procedencia=str(row.get('colegio_procedencia', '')).strip(),
                                municipio_ciudad=str(row.get('municipio_ciudad', '')).strip(),
                                departamento=str(row.get('departamento', '')).strip(),
                                requiere_pago_inscripcion=str(row.get('paga_inscripcion', 'NO')).strip().upper() in ['SI', 'SÍ']
                            )
                            
                            aspirante.procesar_inscripcion_completa()
                            aspirantes_creados_count += 1

                    except (ValueError, Grado.DoesNotExist) as e:
                        errores.append(f"Fila {index + 2}: {e}")
                    except Exception as e:
                        logger.error(f"Error inesperado en fila {index + 2}: {e}", exc_info=True)
                        errores.append(f"Fila {index + 2}: Error inesperado - revise los logs del servidor.")

                if aspirantes_creados_count > 0:
                    messages.success(request, f"✅ Se importaron {aspirantes_creados_count} aspirantes correctamente.")
                if errores:
                    messages.warning(request, "⚠️ Algunas filas no se pudieron importar:")
                    for error in errores:
                        messages.error(request, error)
                
                return redirect('admisiones:lista_grados_aspirantes')

            except Exception as e:
                messages.error(request, f"❌ Error general al procesar el archivo Excel: {e}")
    else:
        form = ImportarAspirantesForm()

    return render(request, 'admisiones/importar_aspirantes.html', {'form': form, 'titulo_pagina': 'Importar Aspirantes desde Excel'})

@login_required
@permission_required('admisiones.view_aspirante', raise_exception=True)
def exportar_matriculados_excel(request):
    """
    Exporta una lista de estudiantes matriculados.
    CORREGIDO: Ahora filtra por la institución del administrador y está completo.
    """
    # Queryset base
    matriculados_qs = Aspirante.objects.filter(
        estado=Aspirante.EstadoAdmision.MATRICULADO
    ).select_related('estudiante_creado__usuario', 'grado_aspira', 'institucion')

    # Aplicamos el filtro de seguridad multi-institución
    if not request.user.is_superuser:
        institucion_usuario = getattr(request.user, 'institucion_asociada', None)
        if institucion_usuario:
            matriculados_qs = matriculados_qs.filter(institucion=institucion_usuario)
        else:
            # Si no tiene institución, no puede exportar nada
            matriculados_qs = Aspirante.objects.none()

    # Construimos el diccionario de datos para el DataFrame
    data = {
        'Nombres': [m.nombres for m in matriculados_qs], 
        'Apellidos': [m.apellidos for m in matriculados_qs],
        'Documento': [m.numero_documento for m in matriculados_qs], 
        'Fecha de Nacimiento': [m.fecha_nacimiento.strftime('%Y-%m-%d') if m.fecha_nacimiento else '' for m in matriculados_qs],
        'Email de Contacto': [m.email_contacto for m in matriculados_qs], 
        'Grado Matriculado': [m.grado_aspira.nombre if m.grado_aspira else 'N/A' for m in matriculados_qs],
        'Sexo': [m.get_sexo_display() for m in matriculados_qs],
        'Colegio de Procedencia': [m.colegio_procedencia for m in matriculados_qs], 
        'Municipio': [m.municipio_ciudad for m in matriculados_qs],
        'Departamento': [m.departamento for m in matriculados_qs],
        'Username Creado': [m.estudiante_creado.usuario.username if m.estudiante_creado and m.estudiante_creado.usuario else 'N/A' for m in matriculados_qs],
    }
    
    # Creamos el archivo Excel en memoria
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Matriculados')
    
    output.seek(0)
    
    # Preparamos la respuesta HTTP para descargar el archivo
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="reporte_matriculados.xlsx"'
    
    return response


@login_required
@permission_required('admisiones.change_aspirante', raise_exception=True)
@transaction.atomic
def revertir_matriculacion(request, aspirante_id):
    """
    Revierte el estado de un aspirante de 'MATRICULADO' a 'ADMITIDO'.
    """
    aspirante = get_object_or_404(Aspirante, pk=aspirante_id, institucion=request.user.institucion_asociada)

    if aspirante.estado != Aspirante.EstadoAdmision.MATRICULADO:
        messages.warning(request, f"El aspirante {aspirante} no está matriculado. No se puede revertir.")
        return redirect('admisiones:lista_aspirantes')

    try:
        estudiante_asociado = aspirante.estudiante_creado
        if estudiante_asociado:
            usuario_asociado = estudiante_asociado.usuario
            
            # 1. Eliminamos al Estudiante
            estudiante_asociado.delete()
            messages.info(request, f"Se eliminó el perfil de estudiante de {estudiante_asociado}.")

            # 2. Lógica para eliminar el Usuario si no tiene otros roles
            if usuario_asociado:
                # Comprobamos si el usuario tiene otros perfiles (ej. docente, familiar)
                # Esta es una forma segura de evitar borrar usuarios multifuncionales.
                if not hasattr(usuario_asociado, 'docente') and not hasattr(usuario_asociado, 'familiar'):
                    usuario_asociado.delete()
                    messages.info(request, f"Se eliminó la cuenta de usuario '{usuario_asociado.username}'.")
                else:
                    messages.warning(request, f"No se eliminó la cuenta de usuario '{usuario_asociado.username}' porque tiene otros perfiles asociados.")

        # 3. Revertimos el estado del Aspirante
        aspirante.estado = Aspirante.EstadoAdmision.ADMITIDO
        aspirante.estudiante_creado = None
        # MEJORA: Usamos update_fields para mayor eficiencia
        aspirante.save(update_fields=['estado', 'estudiante_creado'])

        messages.success(request, f"La matriculación del aspirante {aspirante} ha sido revertida exitosamente.")

    except Exception as e:
        messages.error(request, f"Ocurrió un error al revertir la matriculación: {e}")

    return redirect('admisiones:lista_aspirantes')

@login_required
@permission_required('admisiones.view_aspirante')
def pipeline_admisiones(request):
    """
    Prepara los datos para la vista del pipeline Kanban.
    Agrupa a los aspirantes por su estado de admisión.
    """
    estados_posibles = Aspirante.EstadoAdmision.choices
    
    # ✅ CORRECCIÓN CLAVE:
    # Se corrige la sintaxis del filtro y se usa .exclude()
    aspirantes_activos = Aspirante.objects.filter(
        institucion=request.user.institucion_asociada
    ).exclude(  # <-- Usamos exclude para quitar los que no queremos ver
        estado__in=[Aspirante.EstadoAdmision.RECHAZADO, Aspirante.EstadoAdmision.MATRICULADO]
    ).select_related('grado_aspira').order_by('apellidos', 'nombres')

    # El resto de tu lógica para agrupar es correcta
    pipeline_data = {estado_valor: {'label': estado_label, 'aspirantes': []} for estado_valor, estado_label in estados_posibles}

    for aspirante in aspirantes_activos:
        if aspirante.estado in pipeline_data:
            pipeline_data[aspirante.estado]['aspirantes'].append(aspirante)
    
    # Asegúrate que los valores en columnas_del_pipeline coincidan con los del modelo
    # Por ejemplo, si en el modelo es 'EN_PROCESO', aquí también debe serlo.
    columnas_del_pipeline = [
        Aspirante.EstadoAdmision.INSCRITO, 
        Aspirante.EstadoAdmision.EN_PROCESO, 
        Aspirante.EstadoAdmision.ADMITIDO
    ]
    pipeline_ordenado = {key: pipeline_data[key] for key in columnas_del_pipeline if key in pipeline_data}

    context = {
        'titulo_pagina': "Pipeline de Admisiones",
        'pipeline': pipeline_ordenado,
    }
    return render(request, 'admisiones/pipeline_admisiones.html', context)

@csrf_exempt # Usamos csrf_exempt porque la llamada vendrá de AJAX, pero en producción es mejor usar el token CSRF con JS.
@require_POST
@login_required
@permission_required('admisiones.change_aspirante')
def actualizar_estado_aspirante_api(request):
    """
    Endpoint de API para actualizar el estado de un aspirante.
    Recibe un JSON con el ID del aspirante y el nuevo estado.
    """
    try:
        data = json.loads(request.body)
        aspirante_id = data.get('aspirante_id')
        nuevo_estado = data.get('nuevo_estado')

        # Validamos que el nuevo estado sea válido
        if nuevo_estado not in Aspirante.EstadoAdmision.values:
            return JsonResponse({'status': 'error', 'message': 'Estado no válido.'}, status=400)

        aspirante = get_object_or_404(Aspirante, pk=aspirante_id, institucion=request.user.institucion_asociada)
        
        # Guardamos el estado anterior para la lógica de señales
        estado_anterior = aspirante.estado
        
        if estado_anterior != nuevo_estado:
            aspirante.estado = nuevo_estado
            aspirante.save(update_fields=['estado']) # Actualiza solo el campo de estado
            # La señal post_save se disparará aquí y enviará el correo de cambio de estado.

        return JsonResponse({'status': 'success', 'message': f'Aspirante movido a {aspirante.get_estado_display()}'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
# =========================================================================
# INICIO: VISTAS NUEVAS PARA MERCADO PAGO
# =========================================================================


def crear_preferencia_mercadopago(request, cuenta_por_cobrar_id):
    """
    VERSIÓN FINAL Y ROBUSTA:
    Maneja tanto los pagos de inscripción (vía Estudiante) como los de matrícula (vía Aspirante).
    """
    logger.info(f"Iniciando creación de preferencia para la cuenta: {cuenta_por_cobrar_id}")

    # --- 1. OBTENCIÓN Y VALIDACIÓN DE DATOS ---
    # Obtenemos la cuenta y sus relaciones relacionadas para optimizar.
    cuenta = get_object_or_404(
        CuentaPorCobrarEstudiante.objects.select_related(
            'concepto_pago', 
            'aspirante__institucion', # Para el pago de matrícula
            'estudiante__aspirante_origen__institucion' # Para el pago de inscripción
        ), 
        pk=cuenta_por_cobrar_id
    )
    
    # --- LÓGICA DE BÚSQUEDA INTELIGENTE DEL ASPIRANTE ---
    aspirante = None
    # Caso 1: Pago de Matrícula (la cuenta tiene un enlace directo al aspirante)
    if cuenta.aspirante:
        aspirante = cuenta.aspirante
    # Caso 2: Pago de Inscripción (la cuenta se enlaza a través del estudiante)
    elif cuenta.estudiante and cuenta.estudiante.aspirante_origen:
        aspirante = cuenta.estudiante.aspirante_origen

    # Si después de ambos intentos no encontramos un aspirante, la data es inconsistente.
    if not aspirante:
        logger.error(f"Error Crítico: La CuentaPorCobrarEstudiante ID {cuenta.id} no está vinculada a ningún aspirante válido.")
        raise Http404("No se pudo procesar el pago: la información del aspirante es inconsistente.")

    # --- 2. LÓGICA DE PAGO (DENTRO DE TRY...EXCEPT) ---
    try:
        institucion = aspirante.institucion

        access_token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test
        if not access_token:
            raise ValueError("No se encontraron credenciales de Mercado Pago para esta institución.")

        # Construcción de URLs
        query_params = {'token': aspirante.access_token, 'cuenta_id': cuenta.id}
        base_procesando_url = request.build_absolute_uri(reverse('admisiones:pago_procesando'))
        url_procesando = f"{base_procesando_url}?{urlencode(query_params)}"
        notification_url = request.build_absolute_uri(reverse('admisiones:mercadopago_webhook')) + f"?institucion_id={institucion.id}"
        
        sdk = mercadopago.SDK(access_token)
        
        preference_data = {
            "items": [{"title": f"{cuenta.concepto_pago.nombre_concepto}", "quantity": 1, "unit_price": float(cuenta.monto_asignado), "currency_id": "COP"}],
            "payer": {"name": aspirante.nombres, "surname": aspirante.apellidos, "email": aspirante.email_contacto},
            "back_urls": {"success": url_procesando, "failure": url_procesando, "pending": url_procesando},
            "auto_return": "approved",
            "notification_url": notification_url,
            "external_reference": str(cuenta.id),
        }
        
        logger.info("Enviando los siguientes datos a Mercado Pago: %s", preference_data)
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response.get("status") >= 400:
            error_msg = preference_response['response'].get('message', 'Error desconocido')
            raise ValueError(f"Error de la API de Mercado Pago: {error_msg}")
        
        redirect_url = preference_response['response'].get('sandbox_init_point') or preference_response['response'].get('init_point')
        if not redirect_url:
            raise ValueError("La respuesta de Mercado Pago no contiene una URL de pago válida.")
            
        logger.info(f"Preferencia creada. Redirigiendo a: {redirect_url}")
        return redirect(redirect_url)
        
    except Exception as e:
        logger.error(f"Error creando preferencia de MP para cuenta {cuenta_por_cobrar_id}: {e}", exc_info=True)
        messages.error(request, f"Hubo un error al generar el enlace de pago: {e}")
        return redirect('admisiones:portal_postulante', token=aspirante.access_token)

    

# --- VISTA 2: LA PÁGINA DE ESPERA (SIN CAMBIOS, YA ESTABA BIEN) ---
def pago_respuesta_mp(request):
    """
    Página simple que se muestra al usuario al regresar de Mercado Pago.
    La confirmación real del pago se hace vía Webhook.
    """
    status = request.GET.get('status')
    
    if status == 'approved':
        messages.success(request, "¡Gracias por tu pago! Lo estamos procesando y te confirmaremos en breve.")
    elif status == 'pending':
        messages.info(request, "Tu pago está pendiente. Te notificaremos cuando se apruebe.")
    else: # Failure o cualquier otro caso
        messages.error(request, "El pago no pudo ser completado. Por favor, intenta de nuevo.")
    
    # Aquí puedes agregar lógica para redirigir al portal del aspirante si tienes el token
    return redirect('gestion_academica:inicio_academico')



def subir_documento(request, token, doc_req_id):
    aspirante = get_object_or_404(Aspirante, access_token=token)
    
    if request.method == 'POST':
        # Solo procesamos si realmente se envió un archivo
        if 'archivo' in request.FILES:
            documento_requerido = get_object_or_404(DocumentoRequerido, pk=doc_req_id)
            documento_existente = DocumentoEntregado.objects.filter(aspirante=aspirante, documento_requerido=documento_requerido).first()
            archivo_subido = request.FILES['archivo']

            if documento_existente:
                documento_existente.archivo = archivo_subido
                documento_existente.estado = 'subido'
                documento_existente.save()
                messages.success(request, f"Documento '{documento_requerido.nombre}' reemplazado exitosamente.")
            else:
                DocumentoEntregado.objects.create(aspirante=aspirante, documento_requerido=documento_requerido, archivo=archivo_subido)
                messages.success(request, f"Documento '{documento_requerido.nombre}' subido exitosamente.")
        else:
            # Si se envió el formulario pero sin archivo, mostramos una advertencia
            messages.warning(request, "No se seleccionó ningún archivo para subir.")

    return redirect('admisiones:portal_postulante_pagado', token=token)

def vista_agendamiento(request, token):
    """ Muestra los horarios de citas disponibles para la institución del aspirante. """
    aspirante = get_object_or_404(Aspirante, access_token=token)
    
    if aspirante.estado != 'ADMITIDO':
        messages.warning(request, "Aún no estás en la etapa de agendamiento de citas.")
        return redirect('admisiones:portal_postulante', token=token)
    if hasattr(aspirante, 'cita_agendada'):
        messages.info(request, "Ya tienes una cita agendada.")
        return redirect('admisiones:portal_postulante_pagado', token=token)
    
    # Filtra los horarios por la institución del aspirante
    horarios = HorarioDisponible.objects.filter(
    institucion=aspirante.institucion, 
    fecha_hora_inicio__gte=timezone.now()
    ).annotate(citas_count=Count('citas_agendadas')).filter(citas_count__lt=models.F('cupos_disponibles'))
    
    context = {'aspirante': aspirante, 'horarios_disponibles': horarios, 'titulo_pagina': "Agendar Cita de Admisión"}
    return render(request, 'admisiones/agendar_cita.html', context)

def confirmar_agendamiento(request, token, horario_id):
    aspirante = get_object_or_404(Aspirante, access_token=token)
    horario = get_object_or_404(HorarioDisponible, pk=horario_id, institucion=aspirante.institucion)
    if not horario.esta_disponible or hasattr(aspirante, 'cita_agendada'):
        messages.error(request, "El horario seleccionado ya no está disponible o ya tienes una cita."); return redirect('admisiones:vista_agendamiento', token=token)

    if request.method == 'POST':
        CitaAgendada.objects.create(aspirante=aspirante, horario=horario, notas_adicionales=request.POST.get('notas', ''))
        messages.success(request, f"¡Tu cita ha sido agendada exitosamente!"); return redirect('admisiones:portal_postulante_pagado', token=token)
    
    context = {'aspirante': aspirante, 'horario': horario, 'titulo_pagina': "Confirmar Cita"}
    return render(request, 'admisiones/confirmar_cita.html', context) 

@csrf_exempt
# QUITAMOS @transaction.atomic de aquí para tener control manual
def mercadopago_webhook(request):
    """
    Webhook que procesa notificaciones de Mercado Pago.
    VERSIÓN DEFINITIVA: Usa transacciones manuales para asegurar el registro del pago.
    """
    institucion_id = request.GET.get('institucion_id')
    if not institucion_id:
        logger.error("Webhook MP: Falta el ID de la institución en la URL.")
        return HttpResponse("Falta ID", status=400)

    try:
        data = json.loads(request.body)
        if data.get('type') != 'payment':
            return HttpResponse(status=200)
        
        payment_id = data['data']['id']
        institucion = InstitucionEducativa.objects.get(pk=institucion_id)
        access_token = institucion.mp_access_token_prod if institucion.mp_modo_produccion else institucion.mp_access_token_test
        
        sdk = mercadopago.SDK(access_token)
        payment_info = sdk.payment().get(payment_id)["response"]
        
        if payment_info.get('status') == 'approved':
            external_ref = payment_info.get('external_reference')
            if not external_ref:
                logger.warning(f"Webhook MP: Pago {payment_id} aprobado sin referencia externa.")
                return HttpResponse(status=200)

            # --- INICIO DE LA TRANSACCIÓN CONTROLADA ---
            # En esta "caja de seguridad" solo haremos lo más importante: registrar el pago.
            with transaction.atomic():
                cuenta = CuentaPorCobrarEstudiante.objects.select_for_update().get(id=int(external_ref))
                
                if cuenta.estado == 'PAGADO':
                    logger.info(f"Webhook MP: La cuenta {cuenta.id} ya estaba pagada. Se ignora.")
                    return HttpResponse(status=200)

                aspirante = cuenta.aspirante or (cuenta.estudiante and cuenta.estudiante.aspirante_origen)
                if not aspirante:
                    raise Exception(f"Inconsistencia: Cuenta {cuenta.id} sin aspirante válido.")
                
                estudiante_asociado = aspirante.estudiante_creado
                if not estudiante_asociado:
                    raise Exception(f"Inconsistencia: Aspirante {aspirante.pk} sin estudiante asociado.")

                # 1. Creamos el registro financiero.
                PagoRegistrado.objects.create(
                    cuenta=cuenta, 
                    estudiante=estudiante_asociado,
                    valor_pagado=Decimal(payment_info['transaction_amount']),
                    metodo_pago='MERCADO_PAGO', 
                    referencia_transaccion=str(payment_id), 
                    institucion=institucion,
                    observacion=f"Pago confirmado automáticamente vía MP. ID: {payment_id}"
                )
                logger.info(f"Webhook: PagoRegistrado creado y CONFIRMADO para cuenta #{cuenta.id}.")
            # --- FIN DE LA TRANSACCIÓN CONTROLADA ---

            # En este punto, el PagoRegistrado YA ESTÁ GUARDADO de forma permanente.
            # Nada de lo que pase a continuación puede borrarlo.

            # 2. Ahora, fuera de la transacción principal, ejecutamos el proceso de matrícula.
            try:
                concepto_pagado = cuenta.concepto_pago
                if concepto_pagado.es_pago_matricula and aspirante.estado == 'APROBADO_MATRICULA':
                    # Llamamos a la función del modelo, pero si falla, el pago ya quedó guardado.
                    aspirante.matricular()
                    logger.info(f"Webhook: Aspirante {aspirante.pk} MATRICULADO.")
                
                elif concepto_pagado.es_pago_inscripcion and aspirante.estado == 'INSCRITO':
                    aspirante.estado = 'ADMITIDO'
                    aspirante.save(update_fields=['estado'])
                    logger.info(f"Webhook: Aspirante {aspirante.pk} actualizado a ADMITIDO.")
            except Exception as e:
                # Si la matriculación falla, el pago ya quedó registrado.
                # Ahora podemos registrar el error y notificar al admin para que lo resuelva manualmente.
                logger.error(f"Webhook: El pago para la cuenta {cuenta.id} se registró, pero la matriculación automática falló: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Webhook MP: Error general. {e}", exc_info=True)
        return HttpResponse("Error interno", status=500)
        
    return HttpResponse(status=200)

@login_required # O la forma de autenticación que uses para el portal
def cancelar_cita(request, token):
    """
    Permite a un aspirante cancelar su propia cita agendada.
    """
    # Buscamos al aspirante de forma segura usando el token
    aspirante = get_object_or_404(Aspirante, access_token=token)

    # Verificamos si realmente tiene una cita para cancelar
    try:
        cita_agendada = aspirante.cita_agendada
        
        # Guardamos la información de la cita para el mensaje antes de borrarla
        info_cita_cancelada = str(cita_agendada) 

        # Eliminamos la cita de la base de datos
        cita_agendada.delete()

        # NOTA: Al eliminar la CitaAgendada, el cupo en el HorarioDisponible se libera automáticamente
        # porque la cuenta de 'citas_agendadas' se recalculará.
        
        messages.success(request, f"Tu cita '{info_cita_cancelada}' ha sido cancelada exitosamente. Ya puedes agendar una nueva.")

    except CitaAgendada.DoesNotExist:
        # Esto ocurre si el usuario intenta acceder a la URL pero ya no tiene cita
        messages.warning(request, "No tienes ninguna cita agendada para cancelar.")

    # Siempre redirigimos de vuelta al portal de pagado
    return redirect('admisiones:portal_postulante_pagado', token=token)    

def portal_postulante_pagado(request, token):
    """
    Muestra los siguientes pasos después de que el aspirante ha pagado,
    como la lista de documentos a subir.
    """
    aspirante = get_object_or_404(Aspirante.objects.select_related('institucion'), access_token=token)
    
    # Filtra los documentos requeridos por la institución del aspirante
    documentos_requeridos = DocumentoRequerido.objects.filter(institucion=aspirante.institucion)
    
    # Crea un mapa de los documentos que ya se han subido para mostrarlos en la plantilla
    documentos_subidos = {doc.documento_requerido.id: doc for doc in aspirante.documentos_entregados.all()}
    
    # Prepara la lista de tareas para la plantilla
    lista_tareas_documentos = [
        {'requerido': doc_req, 'entregado': documentos_subidos.get(doc_req.id)} 
        for doc_req in documentos_requeridos
    ]
    
    context = {
        'aspirante': aspirante, 
        'lista_tareas_documentos': lista_tareas_documentos, 
        'titulo_pagina': f"Siguientes Pasos: {aspirante.nombres}"
    }
    return render(request, 'admisiones/portal_postulante_pagado.html', context)


def portal_postulante(request, token):
    """
    Portal único y seguro para el aspirante.
    Muestra el estado de sus documentos y los enlaces de pago correctos,
    buscando en el modelo CuentaPorCobrarEstudiante.
    """
    aspirante = get_object_or_404(Aspirante.objects.select_related(
        'grado_aspira', 'institucion', 'estudiante_creado'
    ), access_token=token)
    
    cuenta_inscripcion = None
    cuenta_matricula = None

    # --- LÓGICA DE BÚSQUEDA DE COBROS CORREGIDA ---
    
    # 1. Si debe pagar INSCRIPCIÓN, buscamos en la tabla de estudiantes,
    #    filtrando por el aspirante y el estado 'PENDIENTE'.
    if aspirante.estado == 'INSCRITO' and aspirante.requiere_pago_inscripcion and aspirante.estudiante_creado:
        cuenta_inscripcion = CuentaPorCobrarEstudiante.objects.filter(
            estudiante=aspirante.estudiante_creado,
            estado='PENDIENTE',
            concepto_pago__nombre_concepto__icontains='Inscripción'
        ).first()

    # 2. Si debe pagar MATRÍCULA, la lógica se mantiene igual.
    elif aspirante.estado == 'APROBADO_MATRICULA':
        # Buscamos la cuenta por cobrar directamente a través del aspirante,
        # que es como se crea en la función 'crear_cuenta_cobro_matricula'.
        cuenta_matricula = CuentaPorCobrarEstudiante.objects.filter(
            aspirante=aspirante,
            estado='PENDIENTE',
            concepto_pago__nombre_concepto__icontains='Matrícula'
        ).first()

    # --- Lógica de documentos (se mantiene igual) ---
    documentos_requeridos = DocumentoRequerido.objects.filter(
        institucion=aspirante.institucion,
        grados_aplicables=aspirante.grado_aspira
    )
    
    documentos_entregados_map = {
        doc.documento_requerido_id: doc 
        for doc in DocumentoEntregado.objects.filter(aspirante=aspirante)
    }

    context = {
        'titulo_pagina': 'Portal del Postulante',
        'aspirante': aspirante,
        'documentos_requeridos': documentos_requeridos,
        'documentos_entregados_map': documentos_entregados_map,
        'cuenta_inscripcion': cuenta_inscripcion,
        'cuenta_matricula': cuenta_matricula,
    }
    return render(request, 'admisiones/portal_postulante.html', context)

@transaction.atomic
def matricular_aspirante(request, aspirante_id):
    """
    Matricula a un aspirante, copiando los valores financieros correctos
    desde el Nivel de Escolaridad asociado a su grado.
    """
    aspirante = get_object_or_404(Aspirante, pk=aspirante_id, institucion=request.user.institucion_asociada)

    # 1. Obtenemos el Nivel de Escolaridad del grado al que aspira.
    grado_aspirado = aspirante.grado_aspira
    nivel_escolaridad = getattr(grado_aspirado, 'nivel_escolaridad', None)

    # 2. Verificamos que el Nivel exista.
    if not nivel_escolaridad:
        messages.error(request, f"Error Crítico: El grado '{grado_aspirado}' no tiene un Nivel de Escolaridad asignado.")
        return redirect('admisiones:detalle_aspirante', pk=aspirante.id)

    # 3. Creamos el perfil de Estudiante, copiando los valores CORRECTOS del Nivel.
    nuevo_estudiante = Estudiante.objects.create(
        usuario=aspirante.usuario,
        institucion=aspirante.institucion,
        documento_identidad=aspirante.numero_documento,
        grado_actual=grado_aspirado,
        # ✅ COPIA LOS VALORES DIRECTAMENTE DEL NIVEL DE ESCOLARIDAD
        valor_matricula=nivel_escolaridad.valor_matricula_estandar,
        valor_mensualidad=nivel_escolaridad.valor_pension_estandar,
        # ... otros campos que quieras copiar del aspirante ...
    )

    # 4. Actualizamos el rol del usuario y el estado del aspirante.
    aspirante.usuario.rol = 'estudiante'
    aspirante.usuario.save(update_fields=['rol'])

    aspirante.estado = Aspirante.EstadoAdmision.MATRICULADO
    aspirante.estudiante_creado = nuevo_estudiante
    aspirante.save(update_fields=['estado', 'estudiante_creado'])

    # La señal post_save de Estudiante ahora se encargará de crear las pensiones
    # usando el `valor_mensualidad` correcto que acabamos de guardar en el perfil.

    messages.success(request, f"¡El aspirante {aspirante} ha sido matriculado exitosamente!")
    return redirect('finanzas:historial_cuentas_estudiante', estudiante_id=nuevo_estudiante.pk)

@login_required
@permission_required('admisiones.change_documentoentregado') # Permiso para revisar
def revision_documentos_lista(request):
    institucion = request.user.institucion_asociada
    
    # Buscamos aspirantes que tengan al menos un documento 'subido'
    aspirantes_con_pendientes = Aspirante.objects.filter(
        institucion=institucion,
        documentos_entregados__estado='subido'
    ).distinct().annotate(
        # Contamos cuántos documentos tiene pendientes cada uno
        documentos_pendientes=Count('documentos_entregados', filter=Q(documentos_entregados__estado='subido'))
    ).order_by('-fecha_inscripcion')

    context = {
        'titulo_pagina': 'Revisión de Documentos',
        'aspirantes': aspirantes_con_pendientes,
    }
    return render(request, 'admisiones/revision_documentos_lista.html', context)

@login_required
@permission_required('admisiones.change_documentoentregado')
def revision_documento_detalle(request, aspirante_id):
    aspirante = get_object_or_404(Aspirante, pk=aspirante_id, institucion=request.user.institucion_asociada)

    # Si el admin envía el formulario para actualizar un documento
    if request.method == 'POST':
        documento_id = request.POST.get('documento_id')
        nuevo_estado = request.POST.get('estado')
        observaciones = request.POST.get('observaciones', '')

        documento = get_object_or_404(DocumentoEntregado, id=documento_id, aspirante=aspirante)
        documento.estado = nuevo_estado
        documento.observaciones_revision = observaciones
        documento.save()
        
        messages.success(request, f"El estado del documento '{documento.documento_requerido.nombre}' ha sido actualizado.")
        return redirect('admisiones:revision_documento_detalle', aspirante_id=aspirante.id)

    # Obtenemos la lista de todos los documentos requeridos y los que ya entregó
    documentos_requeridos = DocumentoRequerido.objects.filter(institucion=aspirante.institucion)
    documentos_entregados = {doc.documento_requerido.id: doc for doc in aspirante.documentos_entregados.all()}
    
    # Unimos la información para la plantilla
    lista_documentos = []
    for requerido in documentos_requeridos:
        lista_documentos.append({
            'requerido': requerido,
            'entregado': documentos_entregados.get(requerido.id)
        })

    context = {
        'titulo_pagina': f'Revisando a {aspirante}',
        'aspirante': aspirante,
        'lista_documentos': lista_documentos,
    }
    return render(request, 'admisiones/revision_documento_detalle.html', context)  

@login_required
@permission_required('admisiones.view_aspirante', raise_exception=True)
def lista_grados_aspirantes(request):
    """
    PÁGINA 1: Muestra una lista de los grados que tienen aspirantes.
    """
    grados_con_aspirantes = Grado.objects.filter(
        institucion=request.user.institucion_asociada
    ).annotate(
        num_aspirantes=Count('aspirante') # 'aspirante' es el related_name por defecto de Aspirante -> Grado
    ).filter(
        num_aspirantes__gt=0
    ).order_by('orden')

    context = {
        'titulo_pagina': "Aspirantes por Grado",
        'grados': grados_con_aspirantes
    }
    return render(request, 'admisiones/lista_grados_aspirantes.html', context)


@login_required
@permission_required('admisiones.view_aspirante', raise_exception=True)
def lista_aspirantes_por_grado(request, grado_id):
    """
    PÁGINA 2: Muestra la lista de aspirantes para un grado específico.
    """
    grado = get_object_or_404(Grado, pk=grado_id, institucion=request.user.institucion_asociada)
    
    aspirantes = Aspirante.objects.filter(
        grado_aspira=grado,
        institucion=request.user.institucion_asociada
    ).select_related('grado_aspira').order_by('apellidos', 'nombres')
    
    context = {
        'titulo_pagina': f"Aspirantes para {grado.nombre}",
        'aspirantes': aspirantes,
        'grado': grado
    }
    return render(request, 'admisiones/lista_aspirantes_por_grado.html', context)          

def pago_procesando(request):
    """
    Página intermedia que verifica el estado del pago y redirige al destino correcto,
    ya sea el portal de admisiones o el dashboard del estudiante.
    """
    cuenta_id = request.GET.get('cuenta_id')
    next_url = request.GET.get('next')  # Leemos el destino final desde la URL

    if not cuenta_id:
        messages.error(request, "Información de pago inválida o incompleta.")
        return redirect('gestion_academica:inicio_academico')

    # --- LÓGICA DE REDIRECCIÓN FINAL ---
    # Si la URL de pago nos dijo a dónde ir (parámetro 'next'), usamos esa URL.
    if next_url:
        url_final = next_url
    else:
        # Si no, usamos la lógica anterior como respaldo para el flujo de admisiones.
        aspirante_token = request.GET.get('token')
        if aspirante_token:
            url_final = reverse('admisiones:portal_postulante_pagado', args=[aspirante_token])
        else:
            # Como último recurso, vamos al inicio.
            url_final = reverse('admisiones:portal_postulante')

    context = {
        'titulo_pagina': 'Procesando tu Pago',
        'cuenta_id': cuenta_id,
        'url_verificacion': reverse('admisiones:verificar_estado_pago', args=[cuenta_id]),
        'url_final': url_final  # Usamos la URL final que acabamos de determinar
    }
    return render(request, 'admisiones/pago_procesando.html', context)

def verificar_estado_pago(request, cuenta_id):
    """
    Endpoint simple que devuelve el estado de una cuenta para ser consultado por AJAX.
    """
    try:
        cuenta = CuentaPorCobrarEstudiante.objects.get(pk=cuenta_id)
        return JsonResponse({'estado': cuenta.estado})
    except CuentaPorCobrarEstudiante.DoesNotExist:
        return JsonResponse({'estado': 'NO_ENCONTRADO'}, status=404)    