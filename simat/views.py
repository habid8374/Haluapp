"""Vistas SIMAT: reporte de matrícula (exportación) y hub.

El exportador genera un Excel con el formato del "Reporte Plano" del SIMAT
(54 columnas) a partir de los aspirantes MATRICULADOS de la institución. Es
multi-institución: solo exporta la institución del usuario (el superusuario
puede pasar ?institucion=<id>). Los campos que HALU aún no captura salen en
blanco (se completan con la Fase 2 de captura).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _


# Orden EXACTO de columnas del Reporte Plano del SIMAT.
COLUMNAS_REPORTE = [
    'ANO', 'ETC', 'ESTADO', 'JERARQUIA', 'INSTITUCION', 'DANE', 'CALENDARIO',
    'SECTOR', 'SEDE', 'CODIGO_DANE_SEDE', 'CONSECUTIVO', 'ZONA_SEDE', 'JORNADA',
    'GRADO_COD', 'GRUPO', 'RENOMBRE', 'MODELO', 'MOTIVO', 'FECHAINI', 'FECHAFIN',
    'NUI', 'ESTRATO', 'SISBEN IV', 'PER_ID', 'DOC', 'TIPODOC', 'APELLIDO1',
    'APELLIDO2', 'NOMBRE1', 'NOMBRE2', 'GENERO', 'FECHA_NACIMIENTO', 'BARRIO',
    'EPS', 'TIPO DE SANGRE', 'MATRICULACONTRATADA', 'FUENTE_RECURSOS', 'INTERNADO',
    'NUM_CONTRATO', 'HA_ESTADO_VINCULADO_SRPA', 'ESTA_ACTIVO_SRPA', 'DISCAPACIDAD',
    'PAIS_ORIGEN', 'CORREO', 'TELEFONO', 'ETNIA', 'TRA_ESP_APR_ESCOLAR',
    'APOYO_ACADEMICO_ESPECIAL', 'LIST_CAP_EXCEPCIONALES', 'CAMPESINO',
    'PAIS_NACIMIENTO', 'PAIS_NACIONALIDAD2', 'CATEGORIA_AULA', 'CONTADOR',
]


def _sn(valor):
    """Bool → 'S'/'N' (formato SIMAT)."""
    return 'S' if valor else 'N'


def _txt(valor):
    return '' if valor is None else str(valor)


def _institucion_de(request):
    """Institución objetivo: la del usuario; superusuario puede pasar ?institucion=."""
    from finanzas.models import InstitucionEducativa
    if request.user.is_superuser and request.GET.get('institucion'):
        return InstitucionEducativa.objects.filter(pk=request.GET['institucion']).first()
    return getattr(request.user, 'institucion_asociada', None)


def _puede_gestionar(user):
    rol = getattr(user, 'rol', '') or ''
    return user.is_superuser or rol in ('coordinador', 'rector', 'administrador', 'secretaria')


def _fila_aspirante(asp, institucion, anio, contador):
    """Arma el dict de una fila del reporte a partir de un Aspirante matriculado."""
    sede = asp.sede
    grado = asp.grado_aspira
    etnia = asp.etnia_simat.nombre if asp.etnia_simat_id else (asp.get_grupo_etnico_display() if asp.grupo_etnico else '')
    eps = asp.eps_simat.nombre if asp.eps_simat_id else _txt(asp.eps)
    fnac = asp.fecha_nacimiento.strftime('%Y-%m-%d') if asp.fecha_nacimiento else ''
    etc = institucion.simat_municipio_etc.codigo if institucion.simat_municipio_etc_id else ''
    # Grupo/sección: prioriza el grupo estructurado del estudiante matriculado;
    # si no, cae al texto libre capturado en la admisión.
    estudiante = getattr(asp, 'estudiante_creado', None)
    if estudiante is not None and getattr(estudiante, 'grupo_id', None):
        grupo_nombre = estudiante.grupo.nombre
    else:
        grupo_nombre = asp.grupo
    return {
        'ANO': anio,
        'ETC': _txt(etc),
        'ESTADO': 'MATRICULADO',
        'JERARQUIA': _txt(etc),
        'INSTITUCION': _txt(institucion.nombre),
        'DANE': _txt(institucion.codigo_dane),
        'CALENDARIO': _txt(institucion.simat_calendario),
        'SECTOR': 'OFICIAL' if institucion.simat_sector == 'OFICIAL' else ('NO OFICIAL' if institucion.simat_sector else ''),
        'SEDE': _txt(sede.nombre) if sede else _txt(institucion.nombre),
        'CODIGO_DANE_SEDE': _txt(sede.codigo_dane_sede) if sede else '',
        'CONSECUTIVO': _txt(sede.consecutivo) if sede else '',
        'ZONA_SEDE': (sede.get_zona_display() if sede and sede.zona else ''),
        'JORNADA': asp.get_jornada_display() if asp.jornada else '',
        'GRADO_COD': _txt(grado.nombre) if grado else '',
        'GRUPO': _txt(grupo_nombre),
        'RENOMBRE': '',
        'MODELO': _txt(asp.modelo_educativo),
        'MOTIVO': '',
        'FECHAINI': '',
        'FECHAFIN': '',
        'NUI': _txt(asp.simat_nui),
        'ESTRATO': asp.get_estrato_display() if asp.estrato else '',
        'SISBEN IV': _txt(asp.sisben_grupo),
        'PER_ID': _txt(asp.simat_per_id),
        'DOC': _txt(asp.numero_documento),
        'TIPODOC': asp.get_tipo_documento_display() if asp.tipo_documento else '',
        'APELLIDO1': _txt(asp.primer_apellido),
        'APELLIDO2': _txt(asp.segundo_apellido),
        'NOMBRE1': _txt(asp.primer_nombre),
        'NOMBRE2': _txt(asp.segundo_nombre),
        'GENERO': asp.get_sexo_display() if asp.sexo else '',
        'FECHA_NACIMIENTO': fnac,
        'BARRIO': _txt(asp.barrio),
        'EPS': eps,
        'TIPO DE SANGRE': _txt(asp.grupo_sanguineo),
        'MATRICULACONTRATADA': _sn(asp.matricula_contratada),
        'FUENTE_RECURSOS': _txt(asp.fuente_recursos),
        'INTERNADO': _txt(asp.internado),
        'NUM_CONTRATO': '',
        'HA_ESTADO_VINCULADO_SRPA': _sn(asp.srpa),
        'ESTA_ACTIVO_SRPA': _sn(asp.srpa),
        'DISCAPACIDAD': asp.get_discapacidad_categoria_display() if asp.discapacidad_categoria else '',
        'PAIS_ORIGEN': _txt(asp.pais_origen),
        'CORREO': _txt(asp.email_contacto),
        'TELEFONO': _txt(asp.telefono_contacto),
        'ETNIA': etnia,
        'TRA_ESP_APR_ESCOLAR': '',
        'APOYO_ACADEMICO_ESPECIAL': _sn(asp.apoyo_academico_especial),
        'LIST_CAP_EXCEPCIONALES': asp.get_capacidad_excepcional_display() if getattr(asp, 'capacidad_excepcional', '') else '',
        'CAMPESINO': _sn(asp.campesino),
        'PAIS_NACIMIENTO': _txt(asp.pais_nacimiento),
        'PAIS_NACIONALIDAD2': _txt(asp.nacionalidad),
        'CATEGORIA_AULA': '',
        'CONTADOR': contador,
    }


@login_required
def exportar_reporte_simat(request):
    """Descarga el Reporte Plano SIMAT (.xlsx) de los matriculados."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from admisiones.models import Aspirante

    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    anio = timezone.now().year

    aspirantes = (
        Aspirante.objects
        .filter(institucion=institucion, estado=Aspirante.EstadoAdmision.MATRICULADO)
        .select_related('sede', 'grado_aspira', 'etnia_simat', 'eps_simat',
                        'estudiante_creado', 'estudiante_creado__grupo')
        .order_by('primer_apellido', 'primer_nombre', 'apellidos')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "REPORTE SIMAT"
    ws.append(COLUMNAS_REPORTE)
    for i, cell in enumerate(ws[1], start=1):
        cell.fill = PatternFill(start_color="0F3460", end_color="0F3460", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF", size=9)
        cell.alignment = Alignment(horizontal='center')

    for idx, asp in enumerate(aspirantes.iterator(), start=1):
        fila = _fila_aspirante(asp, institucion, anio, idx)
        ws.append([fila.get(col, '') for col in COLUMNAS_REPORTE])

    for col_cells in ws.columns:
        w = max((len(str(c.value or '')) for c in col_cells), default=8)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(w + 2, 10), 40)
    ws.freeze_panes = "A2"

    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = f'attachment; filename="reporte_simat_{anio}.xlsx"'
    wb.save(resp)
    return resp


@login_required
def hub_simat(request):
    """Página con el estado de configuración SIMAT y el botón de exportación."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from admisiones.models import Aspirante

    institucion = _institucion_de(request)
    matriculados = 0
    faltan_config = []
    if institucion is not None:
        matriculados = Aspirante.objects.filter(
            institucion=institucion, estado=Aspirante.EstadoAdmision.MATRICULADO
        ).count()
        if not institucion.codigo_dane:
            faltan_config.append("Código DANE de la institución")
        if not institucion.simat_municipio_etc_id:
            faltan_config.append("Municipio (ETC)")
        if not institucion.simat_calendario:
            faltan_config.append("Calendario (A/B)")
        if not institucion.simat_sector:
            faltan_config.append("Sector (oficial/no oficial)")
        if not institucion.sedes.exists():
            faltan_config.append("Al menos una Sede")

    return render(request, 'simat/hub.html', {
        'titulo_pagina': 'Reporte SIMAT',
        'institucion': institucion,
        'matriculados': matriculados,
        'faltan_config': faltan_config,
    })


# ─────────────────────────────────────────────────────────────────────────────
#  CRUD de Sedes (institución-scoped)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lista_sedes(request):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .models import Sede
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    # Garantiza al menos la Sede Principal (por si es una institución antigua).
    Sede.asegurar_principal(institucion)
    sedes = Sede.objects.filter(institucion=institucion).order_by('-es_principal', 'nombre')
    return render(request, 'simat/sedes_lista.html', {
        'titulo_pagina': _('Sedes'),
        'institucion': institucion,
        'sedes': sedes,
    })


@login_required
def crear_sede(request):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .forms import SedeForm
    from .models import Sede
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    if request.method == 'POST':
        form = SedeForm(request.POST)
        if form.is_valid():
            sede = form.save(commit=False)
            sede.institucion = institucion
            # Consecutivo automático (si la institución lo tiene activado y quedó vacío).
            if getattr(institucion, 'simat_consecutivo_sede_automatico', True) and not (sede.consecutivo or '').strip():
                sede.consecutivo = Sede.siguiente_consecutivo(institucion)
            sede.save()
            messages.success(request, _("Sede «%(n)s» creada.") % {'n': sede.nombre})
            return redirect('simat:lista_sedes')
    else:
        initial = {}
        if getattr(institucion, 'simat_consecutivo_sede_automatico', True):
            initial['consecutivo'] = Sede.siguiente_consecutivo(institucion)
        form = SedeForm(initial=initial)
    return render(request, 'simat/sede_form.html', {
        'titulo_pagina': _('Nueva sede'), 'form': form, 'institucion': institucion,
    })


@login_required
def editar_sede(request, pk):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .forms import SedeForm
    from .models import Sede
    institucion = _institucion_de(request)
    sede = get_object_or_404(Sede, pk=pk, institucion=institucion)
    if request.method == 'POST':
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            form.save()
            messages.success(request, _("Sede «%(n)s» actualizada.") % {'n': sede.nombre})
            return redirect('simat:lista_sedes')
    else:
        form = SedeForm(instance=sede)
    return render(request, 'simat/sede_form.html', {
        'titulo_pagina': _('Editar sede'), 'form': form, 'institucion': institucion, 'sede': sede,
    })


@login_required
def eliminar_sede(request, pk):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .models import Sede
    institucion = _institucion_de(request)
    sede = get_object_or_404(Sede, pk=pk, institucion=institucion)
    if request.method == 'POST':
        if sede.es_principal:
            messages.error(request, _("No puedes eliminar la Sede Principal."))
        else:
            nombre = sede.nombre
            sede.delete()
            messages.success(request, _("Sede «%(n)s» eliminada.") % {'n': nombre})
    return redirect('simat:lista_sedes')


# ─────────────────────────────────────────────────────────────────────────────
#  CRUD de Grupos / Secciones (institución-scoped)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lista_grupos(request):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from gestion_academica.models import Grupo
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    grupos = (
        Grupo.objects.filter(institucion=institucion)
        .select_related('grado', 'sede')
        .order_by('grado__orden', 'grado__nombre', 'nombre')
    )
    return render(request, 'simat/grupos_lista.html', {
        'titulo_pagina': _('Grupos'),
        'institucion': institucion,
        'grupos': grupos,
    })


@login_required
def crear_grupo(request):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .forms import GrupoForm
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    if request.method == 'POST':
        form = GrupoForm(request.POST, institucion=institucion)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.institucion = institucion
            grupo.save()
            messages.success(request, _("Grupo «%(n)s» creado.") % {'n': str(grupo)})
            return redirect('simat:lista_grupos')
    else:
        form = GrupoForm(institucion=institucion)
    return render(request, 'simat/grupo_form.html', {
        'titulo_pagina': _('Nuevo grupo'), 'form': form, 'institucion': institucion,
    })


@login_required
def editar_grupo(request, pk):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from .forms import GrupoForm
    from gestion_academica.models import Grupo
    institucion = _institucion_de(request)
    grupo = get_object_or_404(Grupo, pk=pk, institucion=institucion)
    if request.method == 'POST':
        form = GrupoForm(request.POST, instance=grupo, institucion=institucion)
        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.institucion = institucion
            grupo.save()
            messages.success(request, _("Grupo «%(n)s» actualizado.") % {'n': str(grupo)})
            return redirect('simat:lista_grupos')
    else:
        form = GrupoForm(instance=grupo, institucion=institucion)
    return render(request, 'simat/grupo_form.html', {
        'titulo_pagina': _('Editar grupo'), 'form': form, 'institucion': institucion, 'grupo': grupo,
    })


@login_required
def eliminar_grupo(request, pk):
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from gestion_academica.models import Grupo
    institucion = _institucion_de(request)
    grupo = get_object_or_404(Grupo, pk=pk, institucion=institucion)
    if request.method == 'POST':
        if grupo.estudiantes.exists():
            messages.error(
                request,
                _("No puedes eliminar «%(n)s»: tiene estudiantes asignados. "
                  "Muévelos a otro grupo primero.") % {'n': str(grupo)},
            )
        else:
            nombre = str(grupo)
            grupo.delete()
            messages.success(request, _("Grupo «%(n)s» eliminado.") % {'n': nombre})
    return redirect('simat:lista_grupos')
