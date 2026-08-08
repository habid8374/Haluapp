"""Vistas SIMAT: reporte de matrícula (exportación) y hub.

El exportador genera un Excel con el formato del "Reporte Plano" del SIMAT
(54 columnas) a partir de los aspirantes MATRICULADOS de la institución. Es
multi-institución: solo exporta la institución del usuario (el superusuario
puede pasar ?institucion=<id>). Los campos que HALU aún no captura salen en
blanco (se completan con la Fase 2 de captura).
"""
import logging

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


def _si_no(valor):
    """Bool → 'SI'/'NO' (formato SIMAT para campos SI/NO)."""
    return 'SI' if valor else 'NO'


def _txt(valor):
    return '' if valor is None else str(valor)


# ── Tablas de códigos oficiales SIMAT (para exportar CÓDIGO, no la etiqueta) ──
_TIPODOC_SIMAT = {'CC': '1', 'TI': '2', 'CE': '3', 'RC': '5', 'NES': '8', 'PEP': '10', 'VISA': '11', 'TMF': '12'}
_GENERO_SIMAT = {'M': 'M', 'F': 'F'}
_JORNADA_SIMAT = {'COMPLETA': '1', 'MANANA': '2', 'TARDE': '3', 'NOCHE': '4', 'FIN_DE_SEMANA': '5', 'UNICA': '6'}
_ZONA_SIMAT = {'URBANA': '1', 'RURAL': '2'}
_SECTOR_SIMAT = {'OFICIAL': '1001', 'NO_OFICIAL': '1002'}
_DISCAP_SIMAT = {
    'NINGUNA': '99', 'FISICA': '15', 'INTELECTUAL': '8', 'PSICOSOCIAL': '18',
    'VISUAL_BAJA': '3', 'VISUAL_CEGUERA': '4', 'AUDITIVA_HIPOACUSIA': '2',
    'AUDITIVA_SORDA': '1', 'SORDOCEGUERA': '14', 'MULTIPLE': '10', 'SISTEMICA': '17',
    'VOZ_Y_HABLA': '19', 'TEA': '7', 'OTRA': '11',
}
_CAPACID_SIMAT = {
    'NINGUNA': '9', 'GLOBAL': '1', 'TALENTO_CIENTIFICO': '3',
    'TALENTO_ARTISTICO': '4', 'TALENTO_DEPORTIVO': '5', 'OTRA': '',
}
_VICTIMA_SIMAT = {
    'DESPLAZADO': '1', 'DESVINCULADO': '2', 'HIJO_DESMOVILIZADO': '3',
    'VICTIMA_MINAS': '4', 'OTRA': '17',
}


def _cod(mapa, valor):
    """Devuelve el código SIMAT de un valor de choice; '' si no mapea."""
    return mapa.get(valor or '', '')


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
    # Etnia: código oficial SIMAT (no la etiqueta). Sin etnia → '0' (NO APLICA).
    etnia = asp.etnia_simat.codigo if asp.etnia_simat_id else '0'
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
        'SECTOR': _cod(_SECTOR_SIMAT, institucion.simat_sector),
        'SEDE': _txt(sede.nombre) if sede else _txt(institucion.nombre),
        'CODIGO_DANE_SEDE': _txt(sede.codigo_dane_sede) if sede else '',
        'CONSECUTIVO': _txt(sede.consecutivo) if sede else '',
        'ZONA_SEDE': _cod(_ZONA_SIMAT, sede.zona) if sede else '',
        'JORNADA': _cod(_JORNADA_SIMAT, asp.jornada),
        'GRADO_COD': _txt(grado.nombre) if grado else '',
        'GRUPO': _txt(grupo_nombre),
        'RENOMBRE': '',
        'MODELO': _txt(asp.modelo_educativo),
        'MOTIVO': '',
        'FECHAINI': '',
        'FECHAFIN': '',
        'NUI': _txt(asp.simat_nui),
        'ESTRATO': ('NO APLICA' if asp.estrato == '0' else _txt(asp.estrato)),
        'SISBEN IV': _txt(asp.sisben_grupo),
        'PER_ID': _txt(asp.simat_per_id),
        'DOC': _txt(asp.numero_documento),
        'TIPODOC': _cod(_TIPODOC_SIMAT, asp.tipo_documento),
        'APELLIDO1': _txt(asp.primer_apellido),
        'APELLIDO2': _txt(asp.segundo_apellido),
        'NOMBRE1': _txt(asp.primer_nombre),
        'NOMBRE2': _txt(asp.segundo_nombre),
        'GENERO': _cod(_GENERO_SIMAT, asp.sexo),
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
        'DISCAPACIDAD': _cod(_DISCAP_SIMAT, asp.discapacidad_categoria),
        'PAIS_ORIGEN': _txt(asp.pais_origen),
        'CORREO': _txt(asp.email_contacto),
        'TELEFONO': _txt(asp.telefono_contacto),
        'ETNIA': etnia,
        'TRA_ESP_APR_ESCOLAR': '',
        'APOYO_ACADEMICO_ESPECIAL': _sn(asp.apoyo_academico_especial),
        'LIST_CAP_EXCEPCIONALES': _cod(_CAPACID_SIMAT, getattr(asp, 'capacidad_excepcional', '')),
        'CAMPESINO': _sn(asp.campesino),
        'PAIS_NACIMIENTO': _txt(asp.pais_nacimiento),
        'PAIS_NACIONALIDAD2': _txt(asp.nacionalidad),
        'CATEGORIA_AULA': '',
        'CONTADOR': contador,
    }


# ── Encabezado EXACTO del reporte plano del SIMAT (55 columnas, orden oficial) ──
# El SIMAT identifica al alumno por men_per_id / simat_anexo_id (por eso el plano
# NO lleva documento ni nombres: es el anexo que se cruza por ID interno). Lo que
# HALU aún no captura sale vacío (ver auditoría). El Excel conserva los nombres
# legibles para revisión humana.
OFICIAL_COLUMNAS = [
    'simat_anexo_id', 'anio', 'municipio_id', 'dane', 'dane_sede', 'consecutivo_sede', 'sede',
    'prestacion_servicio', 'expedicion_departamento_id', 'expedicion_municipio_id',
    'dir_departamento_id', 'dir_municipio_id', 'estrato_id', 'sisben',
    'nacimiento_departamento_id', 'nacimiento_municipio_id', 'genero_id', 'tipo_victima_id',
    'expulsor_departamento_id', 'expulsor_municipio_id', 'proviene_sector_privado',
    'proviene_otro_municipio', 'discapacidad_id', 'capacidad_id', 'etnia_id', 'resguardo_id',
    'institucion_bienestar', 'jornada_id', 'caracter_id', 'especialidad_id', 'grado_id', 'grupo',
    'metodologia_id', 'subsidiado', 'repitente', 'nuevo', 'situacion_academica_va_id',
    'condicion_alumno_va_id', 'recurso_id', 'zona_id', 'madre_cf', 'hijo_mcf',
    'beneficiario_veterano', 'beneficiario_heroe', 'codigo_internado', 'codigo_valoracion_1',
    'codigo_valoracion_2', 'numero_convenio', 'men_per_id', 'apoyo_acad_esp', 'sist_resp_penal',
    'pais_origen', 'trastorno_id', 'fecha_anexo', 'tipo_anexo_id',
]


def _fk_cod(obj):
    return obj.codigo if obj else ''


def _fila_oficial(asp, institucion, anio, contador):
    """Fila con los nombres/orden EXACTOS del reporte plano del SIMAT. Los campos
    que HALU aún no captura salen vacíos (ver auditoría)."""
    sede = asp.sede
    est = getattr(asp, 'estudiante_creado', None)
    if est is not None and getattr(est, 'grupo_id', None):
        grupo_nombre = est.grupo.nombre
    else:
        grupo_nombre = asp.grupo
    etc = institucion.simat_municipio_etc.codigo if institucion.simat_municipio_etc_id else ''
    tipo_victima = _cod(_VICTIMA_SIMAT, asp.tipo_poblacion_victima) if asp.victima_conflicto else '99'
    return {
        'simat_anexo_id': '',
        'anio': anio,
        'municipio_id': _txt(etc),
        'dane': _txt(institucion.codigo_dane),
        'dane_sede': _txt(sede.codigo_dane_sede) if sede else '',
        'consecutivo_sede': _txt(sede.consecutivo) if sede else '',
        'sede': _txt(sede.nombre) if sede else '',
        'prestacion_servicio': _txt(getattr(institucion, 'simat_prestacion_servicio', '')),
        'expedicion_departamento_id': _fk_cod(asp.lugar_expedicion_departamento),
        'expedicion_municipio_id': _fk_cod(asp.lugar_expedicion_municipio),
        'dir_departamento_id': _fk_cod(asp.departamento_residencia),
        'dir_municipio_id': _fk_cod(asp.municipio_residencia),
        'estrato_id': _txt(asp.estrato),
        'sisben': _txt(asp.sisben_simat),
        'nacimiento_departamento_id': _fk_cod(asp.departamento_nacimiento),
        'nacimiento_municipio_id': _fk_cod(asp.municipio_nacimiento),
        'genero_id': _cod(_GENERO_SIMAT, asp.sexo),
        'tipo_victima_id': tipo_victima,
        'expulsor_departamento_id': _fk_cod(asp.expulsor_departamento),
        'expulsor_municipio_id': _fk_cod(asp.expulsor_municipio),
        'proviene_sector_privado': _txt(asp.proviene_sector_privado),
        'proviene_otro_municipio': _txt(asp.proviene_otro_municipio),
        'discapacidad_id': _cod(_DISCAP_SIMAT, asp.discapacidad_categoria),
        'capacidad_id': _cod(_CAPACID_SIMAT, getattr(asp, 'capacidad_excepcional', '')),
        'etnia_id': asp.etnia_simat.codigo if asp.etnia_simat_id else '0',
        'resguardo_id': _fk_cod(asp.resguardo),
        'institucion_bienestar': _txt(asp.institucion_bienestar),
        'jornada_id': _cod(_JORNADA_SIMAT, asp.jornada),
        'caracter_id': _txt(asp.caracter),
        'especialidad_id': _txt(asp.especialidad),
        'grado_id': _txt(getattr(asp.grado_aspira, 'simat_grado_id', '') if asp.grado_aspira_id else ''),
        'grupo': _txt(grupo_nombre),
        'metodologia_id': _txt(asp.metodologia),
        'subsidiado': _txt(asp.subsidiado),
        'repitente': _si_no(asp.repitente),
        'nuevo': _txt(asp.es_nuevo),
        'situacion_academica_va_id': _txt(asp.situacion_va),
        'condicion_alumno_va_id': _txt(asp.condicion_va),
        'recurso_id': _txt(asp.fuente_recurso),
        'zona_id': _cod(_ZONA_SIMAT, asp.zona_residencia),
        'madre_cf': _txt(asp.madre_cabeza_familia),
        'hijo_mcf': _txt(asp.hijo_madre_cabeza_familia),
        'beneficiario_veterano': _txt(asp.beneficiario_veterano),
        'beneficiario_heroe': _txt(asp.beneficiario_heroe),
        'codigo_internado': _txt(asp.tipo_internado),
        'codigo_valoracion_1': _txt(asp.valoracion_p1),
        'codigo_valoracion_2': _txt(asp.valoracion_p2),
        'numero_convenio': _txt(asp.numero_convenio),
        'men_per_id': _txt(asp.simat_per_id),
        'apoyo_acad_esp': _si_no(asp.apoyo_academico_especial),
        'sist_resp_penal': _si_no(asp.srpa),
        'pais_origen': _txt(asp.pais_origen),
        'trastorno_id': '',
        'fecha_anexo': '',
        'tipo_anexo_id': '',
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


def _escribir_reporte_delimitado(resp, institucion, delimiter=','):
    """Escribe el reporte plano con la estructura OFICIAL del SIMAT (55 columnas,
    orden y nombres exactos). Compartido por .csv (coma) y .txt (tabulador).
    Comillas en valores con el separador (QUOTE_MINIMAL), fin de línea CRLF,
    encoding UTF-8."""
    import csv
    from admisiones.models import Aspirante
    anio = timezone.now().year
    aspirantes = (
        Aspirante.objects
        .filter(institucion=institucion, estado=Aspirante.EstadoAdmision.MATRICULADO)
        .select_related(
            'sede', 'grado_aspira', 'etnia_simat', 'resguardo',
            'estudiante_creado', 'estudiante_creado__grupo',
            'departamento_residencia', 'municipio_residencia',
            'departamento_nacimiento', 'municipio_nacimiento',
            'lugar_expedicion_departamento', 'lugar_expedicion_municipio',
            'expulsor_departamento', 'expulsor_municipio',
        )
        .order_by('primer_apellido', 'primer_nombre', 'apellidos')
    )
    writer = csv.writer(resp, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL, lineterminator='\r\n')
    writer.writerow(OFICIAL_COLUMNAS)
    for idx, asp in enumerate(aspirantes.iterator(), start=1):
        fila = _fila_oficial(asp, institucion, anio, idx)
        writer.writerow([fila.get(col, '') for col in OFICIAL_COLUMNAS])


@login_required
def exportar_reporte_simat_csv(request):
    """Reporte plano SIMAT en CSV (separado por comas). El SIMAT ingesta la
    matrícula como archivo plano; el Excel queda para revisión humana."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    anio = timezone.now().year
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="reporte_simat_{anio}.csv"'
    _escribir_reporte_delimitado(resp, institucion)
    return resp


@login_required
def exportar_reporte_simat_txt(request):
    """Reporte plano SIMAT en .txt (formato oficial: el SIMAT genera el reporte
    'en CSV' pero lo entrega como archivo de texto .txt). Mismo contenido que el
    CSV."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    anio = timezone.now().year
    resp = HttpResponse(content_type='text/plain; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="reporte_simat_{anio}.txt"'
    _escribir_reporte_delimitado(resp, institucion, delimiter='\t')
    return resp


# ─────────────────────────────────────────────────────────────────────────────
#  men_per_id (PER_ID del SIMAT) — carga masiva por Excel (ida y vuelta)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def descargar_plantilla_men_per_id(request):
    """Genera un Excel con los estudiantes matriculados (documento, nombres,
    sede, grado, grupo) y una columna men_per_id para que el usuario la llene con
    el PER_ID que devuelve el SIMAT y la vuelva a subir."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from admisiones.models import Aspirante

    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")

    aspirantes = (
        Aspirante.objects
        .filter(institucion=institucion, estado=Aspirante.EstadoAdmision.MATRICULADO)
        .select_related('sede', 'grado_aspira', 'estudiante_creado', 'estudiante_creado__grupo')
        .order_by('primer_apellido', 'primer_nombre', 'apellidos')
    )
    cols = ['documento', 'apellidos', 'nombres', 'sede', 'grado', 'grupo', 'men_per_id']
    wb = Workbook()
    ws = wb.active
    ws.title = "MEN_PER_ID"
    ws.append(cols)
    for i, cell in enumerate(ws[1], start=1):
        cell.fill = PatternFill(start_color="0F3460", end_color="0F3460", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(horizontal='center')
    for asp in aspirantes.iterator():
        est = getattr(asp, 'estudiante_creado', None)
        grupo = est.grupo.nombre if (est and getattr(est, 'grupo_id', None)) else _txt(asp.grupo)
        apellidos = ' '.join(p for p in [asp.primer_apellido, asp.segundo_apellido] if p) or _txt(asp.apellidos)
        nombres = ' '.join(p for p in [asp.primer_nombre, asp.segundo_nombre] if p) or _txt(asp.nombres)
        ws.append([
            _txt(asp.numero_documento), apellidos, nombres,
            _txt(asp.sede.nombre) if asp.sede else '',
            _txt(asp.grado_aspira.nombre) if asp.grado_aspira_id else '',
            _txt(grupo), _txt(asp.simat_per_id),
        ])
    for col_cells in ws.columns:
        w = max((len(str(c.value or '')) for c in col_cells), default=10)
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(w + 2, 12), 40)
    ws.freeze_panes = "A2"
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename="plantilla_men_per_id.xlsx"'
    wb.save(resp)
    return resp


@login_required
def cargar_men_per_id(request):
    """Recibe el Excel de plantilla_men_per_id con la columna men_per_id llena y
    asigna el PER_ID a cada estudiante (cruzando por documento, en la institución)."""
    if not _puede_gestionar(request.user):
        raise PermissionDenied
    institucion = _institucion_de(request)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")
    if request.method == 'POST' and request.FILES.get('archivo'):
        from openpyxl import load_workbook
        from admisiones.models import Aspirante
        archivo = request.FILES['archivo']
        if not archivo.name.lower().endswith('.xlsx'):
            messages.error(request, _("El archivo debe ser un Excel (.xlsx)."))
            return redirect('simat:hub')
        try:
            wb = load_workbook(archivo, read_only=True, data_only=True)
            ws = wb.active
            filas = ws.iter_rows(values_only=True)
            encabezados = [str(h).strip().lower() if h is not None else '' for h in next(filas)]
            if 'documento' not in encabezados or 'men_per_id' not in encabezados:
                messages.error(request, _("El archivo debe tener las columnas 'documento' y 'men_per_id'."))
                return redirect('simat:hub')
            i_doc = encabezados.index('documento')
            i_men = encabezados.index('men_per_id')
            actualizados, sin_match = 0, 0
            for fila in filas:
                if fila is None or len(fila) <= max(i_doc, i_men):
                    continue
                doc = str(fila[i_doc]).strip() if fila[i_doc] is not None else ''
                men = str(fila[i_men]).strip() if fila[i_men] is not None else ''
                if not doc or not men:
                    continue
                asp = Aspirante.objects.filter(institucion=institucion, numero_documento=doc).first()
                if not asp:
                    sin_match += 1
                    continue
                asp.simat_per_id = men[:20]
                asp.save(update_fields=['simat_per_id'])
                est = getattr(asp, 'estudiante_creado', None)
                if est is not None:
                    car = getattr(est, 'caracterizacion', None)
                    if car is not None:
                        car.simat_per_id = men[:20]
                        car.save(update_fields=['simat_per_id'])
                actualizados += 1
            msg = _("Se asignaron %(n)s PER_ID (men_per_id).") % {'n': actualizados}
            if sin_match:
                msg += _(" %(s)s documento(s) no coincidieron con ningún estudiante.") % {'s': sin_match}
            messages.success(request, msg)
        except Exception:
            logging.getLogger(__name__).exception("Error cargando men_per_id (institución=%s)", getattr(institucion, 'pk', None))
            messages.error(request, _("No se pudo leer el archivo. Verifica que sea el Excel de la plantilla."))
    return redirect('simat:hub')


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
