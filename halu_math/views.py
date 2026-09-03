"""Vistas del módulo Halu Math (práctica adaptativa de matemáticas por DBA)."""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from gestion_academica.models import DBAPredefinido, Estudiante, Grado

from .models import DominioDBA, Dificultad, EjercicioMath, IntentoEjercicioMath, OpcionEjercicioMath
from .motor import elegir_siguiente_ejercicio, procesar_respuesta

logger = logging.getLogger(__name__)

# Piloto v1: solo Matemáticas, grados 3°-5° (operaciones básicas y fracciones).
# Ver plan — se amplía a otros grados/ejes en una Fase 2, sin cambios de esquema.
GRADOS_PILOTO = ['3', '4', '5']


def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


def _es_docente_o_coordinador(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('docente', 'coordinador', 'administrador', 'admin_institucion', 'rector') or user.is_superuser


def _es_estudiante(user):
    return (getattr(user, 'rol', '') or '') == 'estudiante'


def _dbas_piloto():
    return DBAPredefinido.objects.filter(area='matematicas', grado__in=GRADOS_PILOTO).order_by('grado', 'numero')


# ──────────────────────────────────────────────────────────────────────────────
# BANCO DE EJERCICIOS — docente/coordinador
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def banco_ejercicios(request):
    if not _es_docente_o_coordinador(request.user):
        messages.error(request, _("Acceso restringido."))
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)

    qs = EjercicioMath.objects.select_related('dba').prefetch_related('opciones')
    if not request.user.is_superuser:
        qs = qs.filter(Q(es_publica=True) | Q(institucion=institucion))

    dba_sel = request.GET.get('dba', '')
    nivel_sel = request.GET.get('nivel', '')
    if dba_sel:
        qs = qs.filter(dba_id=dba_sel)
    if nivel_sel:
        qs = qs.filter(nivel_dificultad=nivel_sel)

    return render(request, 'halu_math/banco_ejercicios.html', {
        'ejercicios': qs.order_by('dba', 'nivel_dificultad'),
        'dbas': _dbas_piloto(),
        'niveles': Dificultad.choices,
        'dba_sel': dba_sel,
        'nivel_sel': nivel_sel,
        'titulo_pagina': _('Halu Math — Banco de Ejercicios'),
    })


@login_required
def crear_ejercicio(request):
    if not _es_docente_o_coordinador(request.user):
        return redirect('gestion_academica:inicio_academico')

    if request.method == 'POST':
        return _guardar_ejercicio(request, None)

    return render(request, 'halu_math/form_ejercicio.html', {
        'dbas': _dbas_piloto(),
        'niveles': Dificultad.choices,
        'titulo_pagina': _('Nuevo Ejercicio'),
        'accion': _('Crear'),
    })


@login_required
def editar_ejercicio(request, pk):
    if not _es_docente_o_coordinador(request.user):
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    ejercicio = get_object_or_404(
        EjercicioMath, pk=pk,
        **({} if request.user.is_superuser else {'institucion': institucion}),
    )

    if request.method == 'POST':
        return _guardar_ejercicio(request, ejercicio)

    opciones = {o.letra: o.texto for o in ejercicio.opciones.all()}
    correcta = ejercicio.opciones.filter(es_correcta=True).values_list('letra', flat=True).first()

    return render(request, 'halu_math/form_ejercicio.html', {
        'ejercicio': ejercicio,
        'opciones': opciones,
        'correcta': correcta,
        'dbas': _dbas_piloto(),
        'niveles': Dificultad.choices,
        'titulo_pagina': _('Editar Ejercicio'),
        'accion': _('Guardar'),
    })


def _guardar_ejercicio(request, ejercicio_existente):
    institucion = _get_institucion(request)
    p = request.POST

    enunciado = (p.get('enunciado') or '').strip()
    if not enunciado:
        messages.error(request, _("El enunciado no puede estar vacío."))
        return redirect(request.path)

    dba = _dbas_piloto().filter(pk=p.get('dba')).first()
    if not dba:
        messages.error(request, _("Selecciona un DBA válido."))
        return redirect(request.path)

    correcta = p.get('correcta', 'A')
    opciones_texto = {l: (p.get(f'opcion_{l}') or '').strip() for l in 'ABCD'}
    if not all(opciones_texto.values()):
        messages.error(request, _("Debes completar las 4 opciones."))
        return redirect(request.path)

    if ejercicio_existente is None:
        ejercicio_existente = EjercicioMath(
            institucion=institucion,
            es_publica=False,
            creado_por=request.user,
        )

    ejercicio_existente.dba = dba
    ejercicio_existente.enunciado = enunciado
    ejercicio_existente.nivel_dificultad = p.get('nivel_dificultad', Dificultad.BASICO)
    ejercicio_existente.explicacion = (p.get('explicacion') or '').strip()
    ejercicio_existente.fuente = (p.get('fuente') or '').strip()
    ejercicio_existente.save()

    ejercicio_existente.opciones.all().delete()
    for letra in 'ABCD':
        OpcionEjercicioMath.objects.create(
            ejercicio=ejercicio_existente,
            letra=letra,
            texto=opciones_texto[letra],
            es_correcta=(letra == correcta),
        )

    messages.success(request, _("Ejercicio guardado correctamente."))
    return redirect('halu_math:banco_ejercicios')


@login_required
@require_POST
def eliminar_ejercicio(request, pk):
    if not _es_docente_o_coordinador(request.user):
        return redirect('gestion_academica:inicio_academico')
    institucion = _get_institucion(request)
    ejercicio = get_object_or_404(
        EjercicioMath, pk=pk,
        **({} if request.user.is_superuser else {'institucion': institucion, 'es_publica': False}),
    )
    ejercicio.delete()
    messages.success(request, _("Ejercicio eliminado."))
    return redirect('halu_math:banco_ejercicios')


# ──────────────────────────────────────────────────────────────────────────────
# GENERACIÓN CON IA (Gemini) — dos fases, mismo patrón que Simulacros
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
@ratelimit(key='user', rate='10/h', method='POST', block=True)
def generar_ia(request):
    if not _es_docente_o_coordinador(request.user):
        return JsonResponse({'ok': False, 'error': 'Sin permiso.'}, status=403)

    dba_id = request.POST.get('dba_id')
    try:
        cantidad = min(int(request.POST.get('cantidad', 5)), 10)
    except (TypeError, ValueError):
        cantidad = 5
    dificultad = request.POST.get('dificultad', Dificultad.BASICO)

    dba = _dbas_piloto().filter(pk=dba_id).first()
    if not dba:
        return JsonResponse({'ok': False, 'error': 'DBA inválido.'}, status=400)
    dif_label = dict(Dificultad.choices).get(dificultad, dificultad)

    prompt = f"""Eres un experto en pedagogía de las matemáticas para educación básica en Colombia.
Genera exactamente {cantidad} ejercicios de opción múltiple con única respuesta para practicar el siguiente
Derecho Básico de Aprendizaje (DBA) de Matemáticas, {dba.get_grado_display()}:

"{dba.enunciado}"

Evidencias de aprendizaje asociadas: {dba.evidencias or 'No especificadas.'}

Nivel de dificultad de los ejercicios: {dif_label}.

Formato estricto de respuesta — JSON puro, sin markdown, sin texto antes ni después:
[
  {{
    "enunciado": "texto completo del ejercicio, con un problema o situación concreta",
    "opciones": {{"A": "texto A", "B": "texto B", "C": "texto C", "D": "texto D"}},
    "correcta": "A",
    "explicacion": "explicación breve y sencilla de por qué es correcta, apta para un niño de este grado"
  }}
]

Reglas:
- Los ejercicios deben ser apropiados para {dba.get_grado_display()} de primaria en Colombia.
- Las opciones incorrectas (distractores) deben reflejar errores comunes de cálculo, no ser absurdas.
- La respuesta correcta debe ser inequívoca.
- No uses LaTeX ni HTML, solo texto plano con números y símbolos matemáticos simples (+, -, x, ÷, fracciones como 1/2).
"""

    try:
        from finanzas.institucion_credentials import google_api_key as get_google_api_key
        from finanzas import ia as _ia_gate
        institucion = getattr(request.user, 'institucion_asociada', None)
        _api_key = get_google_api_key(institucion) if institucion else None
        if not _api_key:
            return JsonResponse({'ok': False, 'error': 'La institución no tiene Google API Key configurada.'}, status=400)
        try:
            resp = _ia_gate.gemini_generate(institucion, 'gemini-2.0-flash', prompt)
        except _ia_gate.IATopeSuperado as _e:
            return JsonResponse({'ok': False, 'error': str(_e)}, status=200)
        raw = resp.text.strip()

        if raw.startswith('```'):
            raw = raw.split('```')[1]
            if raw.startswith('json'):
                raw = raw[4:]
        ejercicios_data = json.loads(raw)

        # M5 — validar estructura básica antes de enviar al cliente
        if not isinstance(ejercicios_data, list) or not ejercicios_data:
            raise ValueError("La IA no devolvió una lista de ejercicios válida.")
        for e in ejercicios_data:
            if not isinstance(e, dict) or not e.get('enunciado') or not isinstance(e.get('opciones'), dict):
                raise ValueError("Estructura de ejercicio inválida en la respuesta de la IA.")

        return JsonResponse({'ok': True, 'ejercicios': ejercicios_data, 'dba_id': dba.pk, 'dificultad': dificultad})
    except Exception as exc:
        logger.error("halu_math.generar_ia error: %s", exc, exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error al generar ejercicios. Intenta de nuevo.'}, status=500)


@login_required
@require_POST
@ratelimit(key='user', rate='20/h', method='POST', block=True)
def guardar_ia(request):
    """Guarda en el banco los ejercicios generados por IA tras revisión del docente."""
    if not _es_docente_o_coordinador(request.user):
        return JsonResponse({'ok': False, 'error': 'Sin permiso.'}, status=403)

    institucion = _get_institucion(request)
    try:
        data = json.loads(request.body)
        ejercicios_raw = data.get('ejercicios', [])
        if not isinstance(ejercicios_raw, list) or not ejercicios_raw:
            return JsonResponse({'ok': False, 'error': 'Datos inválidos.'}, status=400)

        # A02/A08 — validar valores contra choices/catálogo permitidos
        dif_validas = {v for v, _lbl in Dificultad.choices}
        dificultad = data.get('dificultad', Dificultad.BASICO)
        if dificultad not in dif_validas:
            return JsonResponse({'ok': False, 'error': 'Parámetros inválidos.'}, status=400)

        dba = _dbas_piloto().filter(pk=data.get('dba_id')).first()
        if not dba:
            return JsonResponse({'ok': False, 'error': 'DBA inválido.'}, status=400)

        creados = 0
        for e in ejercicios_raw[:10]:  # máximo 10 ejercicios por llamada
            enunciado = str(e.get('enunciado', '')).strip()[:3000]
            if not enunciado:
                continue
            opciones = e.get('opciones', {})
            if not isinstance(opciones, dict):
                continue
            correcta = str(e.get('correcta', 'A')).strip().upper()
            if correcta not in 'ABCD':
                correcta = 'A'

            ejercicio = EjercicioMath.objects.create(
                institucion=institucion,
                es_publica=False,
                dba=dba,
                nivel_dificultad=dificultad,
                enunciado=enunciado,
                explicacion=str(e.get('explicacion', ''))[:2000],
                fuente='Generado con IA (Gemini)',
                creado_por=request.user,
            )
            for letra in 'ABCD':
                texto_opcion = str(opciones.get(letra, '')).strip()[:300]
                OpcionEjercicioMath.objects.create(
                    ejercicio=ejercicio,
                    letra=letra,
                    texto=texto_opcion or f'Opción {letra}',
                    es_correcta=(letra == correcta),
                )
            creados += 1

        return JsonResponse({'ok': True, 'creados': creados})
    except Exception as exc:
        logger.error("halu_math.guardar_ia error: %s", exc, exc_info=True)
        return JsonResponse({'ok': False, 'error': 'Error al guardar ejercicios.'}, status=500)


# ──────────────────────────────────────────────────────────────────────────────
# DASHBOARD DOCENTE — progreso del grupo
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def progreso_grupo(request):
    if not _es_docente_o_coordinador(request.user):
        messages.error(request, _("Acceso restringido."))
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    grados = Grado.objects.filter(institucion=institucion).order_by('nombre')
    grado_sel = request.GET.get('grado', '')
    dbas = _dbas_piloto()
    matriz = []
    estudiantes = Estudiante.objects.none()

    if grado_sel:
        estudiantes = Estudiante.objects.filter(
            institucion=institucion, grado_actual_id=grado_sel,
        ).select_related('usuario').order_by('usuario__first_name', 'usuario__last_name')
        dominios = {
            (d.estudiante_id, d.dba_id): d
            for d in DominioDBA.objects.filter(institucion=institucion, estudiante__in=estudiantes, dba__in=dbas)
        }
        for est in estudiantes:
            matriz.append({
                'estudiante': est,
                'celdas': [dominios.get((est.pk, dba.pk)) for dba in dbas],
            })

    total_intentos = IntentoEjercicioMath.objects.filter(institucion=institucion, estudiante__in=estudiantes).count()
    total_dominados = DominioDBA.objects.filter(institucion=institucion, estudiante__in=estudiantes, dominado=True).count()
    aciertos = IntentoEjercicioMath.objects.filter(institucion=institucion, estudiante__in=estudiantes, es_correcta=True).count()
    pct_acierto = round(aciertos / total_intentos * 100, 1) if total_intentos else 0

    return render(request, 'halu_math/progreso_grupo.html', {
        'grados': grados,
        'grado_sel': grado_sel,
        'dbas': dbas,
        'matriz': matriz,
        'total_intentos': total_intentos,
        'total_dominados': total_dominados,
        'pct_acierto': pct_acierto,
        'titulo_pagina': _('Halu Math — Progreso del grupo'),
    })


@login_required
def progreso_estudiante(request, estudiante_pk):
    if not _es_docente_o_coordinador(request.user):
        messages.error(request, _("Acceso restringido."))
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    estudiante = get_object_or_404(Estudiante, pk=estudiante_pk, institucion=institucion)
    dominios = DominioDBA.objects.filter(
        institucion=institucion, estudiante=estudiante,
    ).select_related('dba').order_by('dba__grado', 'dba__numero')

    return render(request, 'halu_math/progreso_estudiante.html', {
        'estudiante': estudiante,
        'dominios': dominios,
        'titulo_pagina': _('Progreso — %(nombre)s') % {'nombre': estudiante.usuario.get_full_name() or estudiante.usuario.username},
    })


# ──────────────────────────────────────────────────────────────────────────────
# VISTAS DEL ESTUDIANTE
# ──────────────────────────────────────────────────────────────────────────────

@login_required
def elegir_dba(request):
    if not _es_estudiante(request.user):
        messages.error(request, _("Esta sección es solo para estudiantes."))
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    estudiante = getattr(request.user, 'estudiante', None)
    if not estudiante:
        messages.error(request, _("No tienes perfil de estudiante."))
        return redirect('gestion_academica:inicio_academico')

    dbas = _dbas_piloto().filter(
        Q(ejercicios_math__es_publica=True) | Q(ejercicios_math__institucion=institucion),
    ).distinct()
    dominios = {d.dba_id: d for d in DominioDBA.objects.filter(estudiante=estudiante, dba__in=dbas)}

    filas = [{'dba': dba, 'dominio': dominios.get(dba.pk)} for dba in dbas]

    return render(request, 'halu_math/elegir_dba.html', {
        'filas': filas,
        'titulo_pagina': _('Halu Math — Practicar'),
    })


@login_required
def practicar_dba(request, dba_pk):
    if not _es_estudiante(request.user):
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    estudiante = getattr(request.user, 'estudiante', None)
    if not estudiante:
        messages.error(request, _("No tienes perfil de estudiante."))
        return redirect('gestion_academica:inicio_academico')

    dba = get_object_or_404(_dbas_piloto(), pk=dba_pk)
    dominio, _creado = DominioDBA.objects.get_or_create(
        estudiante=estudiante, dba=dba, defaults={'institucion': institucion},
    )

    ejercicio = elegir_siguiente_ejercicio(dominio, institucion)
    if not ejercicio:
        messages.info(request, _("Aún no hay ejercicios disponibles para este DBA. Pídele a tu docente que genere algunos."))
        return redirect('halu_math:elegir_dba')

    return render(request, 'halu_math/practicar_dba.html', {
        'dba': dba,
        'dominio': dominio,
        'ejercicio': ejercicio,
        'opciones': ejercicio.opciones.all(),
        'titulo_pagina': dba.enunciado,
    })


@login_required
@require_POST
def responder_ejercicio(request, dba_pk):
    if not _es_estudiante(request.user):
        return JsonResponse({'ok': False, 'error': 'Sin permiso.'}, status=403)

    institucion = _get_institucion(request)
    estudiante = getattr(request.user, 'estudiante', None)
    if not estudiante:
        return JsonResponse({'ok': False, 'error': 'Sin perfil de estudiante.'}, status=403)

    dba = get_object_or_404(_dbas_piloto(), pk=dba_pk)
    dominio = get_object_or_404(DominioDBA, estudiante=estudiante, dba=dba, institucion=institucion)

    ejercicio = get_object_or_404(EjercicioMath, pk=request.POST.get('ejercicio_id'), dba=dba)
    # IDOR: el ejercicio debe ser público o de la propia institución del estudiante
    # (mismo guard que simulacros/views.py:596-610 — nunca confiar en el pk sin re-filtrar).
    if not (ejercicio.es_publica or (institucion and ejercicio.institucion_id == institucion.id)):
        return JsonResponse({'ok': False, 'error': 'Ejercicio no disponible.'}, status=403)

    opcion_id = request.POST.get('opcion_id')
    opcion = OpcionEjercicioMath.objects.filter(pk=opcion_id, ejercicio=ejercicio).first() if opcion_id else None
    es_correcta = bool(opcion and opcion.es_correcta)

    IntentoEjercicioMath.objects.create(
        institucion=institucion, estudiante=estudiante, ejercicio=ejercicio,
        opcion_elegida=opcion, es_correcta=es_correcta, nivel_en_el_momento=dominio.nivel_actual,
    )

    nivel_antes = dominio.nivel_actual
    dominado_antes = dominio.dominado
    dominio = procesar_respuesta(dominio, es_correcta)

    opcion_correcta = ejercicio.opcion_correcta

    return JsonResponse({
        'ok': True,
        'es_correcta': es_correcta,
        'explicacion': ejercicio.explicacion,
        'letra_correcta': opcion_correcta.letra if opcion_correcta else None,
        'nivel_actual': dominio.nivel_actual,
        'nivel_actual_label': dominio.get_nivel_actual_display(),
        'racha_actual': dominio.racha_actual,
        'subio_nivel': dominio.nivel_actual != nivel_antes,
        'dominado': dominio.dominado,
        'recien_dominado': dominio.dominado and not dominado_antes,
    })


@login_required
def mi_progreso_math(request):
    if not _es_estudiante(request.user):
        return redirect('gestion_academica:inicio_academico')

    estudiante = getattr(request.user, 'estudiante', None)
    if not estudiante:
        messages.error(request, _("No tienes perfil de estudiante."))
        return redirect('gestion_academica:inicio_academico')

    dominios = DominioDBA.objects.filter(estudiante=estudiante).select_related('dba').order_by('dba__grado', 'dba__numero')

    return render(request, 'halu_math/mi_progreso_math.html', {
        'dominios': dominios,
        'titulo_pagina': _('Mi Progreso — Halu Math'),
    })
