# gestion_academica/urls.py
from django.urls import path
from . import views
from .views import cuentas_por_estudiante
from django.views.generic import RedirectView
from gestion_academica.views import registro_inicial


app_name = 'gestion_academica'

urlpatterns = [
    path('registro_inicial/', registro_inicial, name='registro_inicial'),

    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    # Inicio
    path('', views.inicio_academico, name='inicio_academico'),

    # Grados
    path('grados/', views.GradoListView.as_view(), name='lista_grados'),
    path('grados/crear/', views.GradoCreateView.as_view(), name='crear_grado'),
    path('grados/<int:pk>/editar/', views.GradoUpdateView.as_view(), name='editar_grado'),
    path('grados/<int:pk>/eliminar/', views.GradoDeleteView.as_view(), name='eliminar_grado'),

    # Estudiantes (Gestión)
    path('estudiantes/', views.EstudianteListView.as_view(), name='lista_estudiantes'),
    path('estudiantes/crear/', views.crear_estudiante, name='crear_estudiante'),
    path('estudiantes/<int:pk>/', views.EstudianteDetailView.as_view(), name='detalle_estudiante'),
    path('estudiantes/<int:pk>/editar/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiantes/<int:pk>/eliminar/', views.EstudianteDeleteView.as_view(), name='eliminar_estudiante'),

    # Docentes (Gestión)
    path('docentes/', views.DocenteListView.as_view(), name='lista_docentes'),
    path('docentes/crear/', views.crear_docente, name='crear_docente'),
    path('docentes/<int:pk>/', views.DocenteDetailView.as_view(), name='detalle_docente'),
    path('docentes/<int:pk>/editar/', views.editar_docente, name='editar_docente'),
    path('docentes/<int:pk>/eliminar/', views.DocenteDeleteView.as_view(), name='eliminar_docente'),

    # Materias
    path('materias/', views.MateriaListView.as_view(), name='lista_materias'),
    path('materias/crear/', views.MateriaCreateView.as_view(), name='crear_materia'),
    path('materias/<int:pk>/editar/', views.MateriaUpdateView.as_view(), name='editar_materia'),
    path('materias/<int:pk>/eliminar/', views.MateriaDeleteView.as_view(), name='eliminar_materia'),

    # Periodos Académicos
    path('periodos/', views.PeriodoAcademicoListView.as_view(), name='lista_periodos'),
    path('periodos/crear/', views.PeriodoAcademicoCreateView.as_view(), name='crear_periodo'),
    path('periodos/<int:pk>/editar/', views.PeriodoAcademicoUpdateView.as_view(), name='editar_periodo'),
    path('periodos/<int:pk>/eliminar/', views.PeriodoAcademicoDeleteView.as_view(), name='eliminar_periodo'),

    # Cursos
    path('cursos/', views.CursoListView.as_view(), name='lista_cursos'),
    path('cursos/crear/', views.CursoCreateView.as_view(), name='crear_curso'),
    path('cursos/<int:pk>/', views.CursoDetailView.as_view(), name='detalle_curso'),
    path('cursos/<int:pk>/editar/', views.CursoUpdateView.as_view(), name='editar_curso'),
    path('cursos/<int:pk>/eliminar/', views.CursoDeleteView.as_view(), name='eliminar_curso'),

    # Directores de Curso
    path('directores-curso/', views.DirectorCursoListView.as_view(), name='lista_directores_curso'),
    path('directores-curso/asignar/', views.DirectorCursoCreateView.as_view(), name='crear_director_curso'),
    path('directores-curso/<int:pk>/editar/', views.DirectorCursoUpdateView.as_view(), name='editar_director_curso'),
    path('directores-curso/<int:pk>/eliminar/', views.DirectorCursoDeleteView.as_view(), name='eliminar_director_curso'),

    # Esquemas de Calificación
    path('esquemas-calificacion/', views.EsquemaCalificacionListView.as_view(), name='lista_esquemas_calificacion'),
    path('esquemas-calificacion/crear/', views.EsquemaCalificacionCreateView.as_view(), name='crear_esquema_calificacion'),
    path('esquemas-calificacion/<int:pk>/editar/', views.EsquemaCalificacionUpdateView.as_view(), name='editar_esquema_calificacion'),
    path('esquemas-calificacion/<int:pk>/eliminar/', views.EsquemaCalificacionDeleteView.as_view(), name='eliminar_esquema_calificacion'),

    # Tipos de Actividad
    path('tipos-actividad/', views.TipoActividadListView.as_view(), name='lista_tipos_actividad'),
    path('tipos-actividad/crear/', views.TipoActividadCreateView.as_view(), name='crear_tipo_actividad'),
    path('tipos-actividad/<int:pk>/editar/', views.TipoActividadUpdateView.as_view(), name='editar_tipo_actividad'),
    path('tipos-actividad/<int:pk>/eliminar/', views.TipoActividadDeleteView.as_view(), name='eliminar_tipo_actividad'),

    # Actividades Calificables
    path('actividades/', views.ActividadCalificableListView.as_view(), name='lista_actividades_calificables'),
    path('actividades/crear/', views.ActividadCalificableCreateView.as_view(), name='crear_actividad_calificable'),
    path('actividades/<int:pk>/', views.ActividadCalificableDetailView.as_view(), name='detalle_actividad_calificable'),
    path('actividades/<int:pk>/editar/', views.ActividadCalificableUpdateView.as_view(), name='editar_actividad_calificable'),
    path('actividades/<int:pk>/eliminar/', views.ActividadCalificableDeleteView.as_view(), name='eliminar_actividad_calificable'),
    
    # Registro de Calificaciones (Docentes)
    path('actividad/<int:actividad_pk>/calificar/', views.listar_estudiantes_para_calificar, name='listar_estudiantes_para_calificar'),
    path('actividad/<int:actividad_pk>/calificar/estudiante/<int:estudiante_pk>/', views.registrar_editar_calificacion, name='registrar_editar_calificacion'),

    # Deberes / Tareas (Gestión por Docente/Admin)
    path('deberes/', views.DeberListView.as_view(), name='lista_deberes'),
    path('deberes/crear/', views.DeberCreateView.as_view(), name='crear_deber'),
    path('deberes/<int:pk>/', views.DeberDetailView.as_view(), name='detalle_deber'),
    path('deberes/<int:pk>/editar/', views.DeberUpdateView.as_view(), name='editar_deber'),
    path('deberes/<int:pk>/eliminar/', views.DeberDeleteView.as_view(), name='eliminar_deber'),

    # Planes Curriculares
    path('planes-curriculares/', views.PlanCurricularListView.as_view(), name='lista_planes_curriculares'),
    path('planes-curriculares/crear/', views.PlanCurricularCreateView.as_view(), name='crear_plan_curricular'),
    path('planes-curriculares/<int:pk>/', views.PlanCurricularDetailView.as_view(), name='detalle_plan_curricular'),
    path('planes-curriculares/<int:pk>/editar/', views.PlanCurricularUpdateView.as_view(), name='editar_plan_curricular'),
    path('planes-curriculares/<int:pk>/eliminar/', views.PlanCurricularDeleteView.as_view(), name='eliminar_plan_curricular'),

    # Menciones y Reconocimientos
    path('menciones/', views.MencionReconocimientoListView.as_view(), name='lista_menciones'),
    path('menciones/registrar/', views.MencionReconocimientoCreateView.as_view(), name='crear_mencion'),
    path('menciones/<int:pk>/editar/', views.MencionReconocimientoUpdateView.as_view(), name='editar_mencion'),
    path('menciones/<int:pk>/eliminar/', views.MencionReconocimientoDeleteView.as_view(), name='eliminar_mencion'),

    # Archivos de Planes Académicos y Materiales
    path('archivos-planes/', views.ArchivoPlanAcademicoListView.as_view(), name='lista_archivos_plan'),
    path('archivos-planes/subir/', views.ArchivoPlanAcademicoCreateView.as_view(), name='crear_archivo_plan'),
    path('archivos-planes/<int:pk>/editar/', views.ArchivoPlanAcademicoUpdateView.as_view(), name='editar_archivo_plan'),
    path('archivos-planes/<int:pk>/eliminar/', views.ArchivoPlanAcademicoDeleteView.as_view(), name='eliminar_archivo_plan'),

    # Estudiantes (Portal del Estudiante)
    path('mis-calificaciones/', views.mis_cursos_y_calificaciones_resumen, name='mis_cursos_calificaciones'),
    path('mis-calificaciones/curso/<int:curso_pk>/', views.detalle_mis_calificaciones_por_curso, name='detalle_mis_calificaciones_por_curso'),
    path('mi-boletin/', views.mi_boletin_periodo_actual, name='mi_boletin_periodo_actual'),
    path('mis-deberes/', views.mis_deberes_lista, name='mis_deberes_lista'),
    path('deber/<int:deber_pk>/entregar/', views.realizar_entrega_deber, name='realizar_entrega_deber'),

    # Portal de Familiares
    path('portal-familiar/', views.portal_familiar_inicio, name='portal_familiar_inicio'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/calificaciones/', views.familiar_ver_calificaciones_estudiante, name='familiar_ver_calificaciones_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/calificaciones/curso/<int:curso_pk>/', views.familiar_ver_detalle_calificaciones_curso_estudiante, name='familiar_ver_detalle_calificaciones_curso_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/boletin/', views.familiar_ver_boletin_estudiante, name='familiar_ver_boletin_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/deberes/', views.familiar_ver_deberes_estudiante, name='familiar_ver_deberes_estudiante'),

    # Tipos de Concepto de Pago
    path('tipos-concepto-pago/', views.TipoConceptoPagoListView.as_view(), name='lista_tipos_concepto_pago'),
    path('tipos-concepto-pago/crear/', views.TipoConceptoPagoCreateView.as_view(), name='crear_tipo_concepto_pago'),
    path('tipos-concepto-pago/<int:pk>/editar/', views.TipoConceptoPagoUpdateView.as_view(), name='editar_tipo_concepto_pago'),
    path('tipos-concepto-pago/<int:pk>/eliminar/', views.TipoConceptoPagoDeleteView.as_view(), name='eliminar_tipo_concepto_pago'),

    # Conceptos de Pago
    path('conceptos-pago/', views.ConceptoPagoListView.as_view(), name='lista_conceptos_pago'),
    path('conceptos-pago/crear/', views.ConceptoPagoCreateView.as_view(), name='crear_concepto_pago'),
    path('conceptos-pago/<int:pk>/editar/', views.ConceptoPagoUpdateView.as_view(), name='editar_concepto_pago'),
    path('conceptos-pago/<int:pk>/eliminar/', views.ConceptoPagoDeleteView.as_view(), name='eliminar_concepto_pago'),

    # Docentes - Libro de Notas
    path('docente/libro-notas/', views.docente_seleccionar_curso_libro_notas, name='docente_seleccionar_curso_libro_notas'),
    path('docente/libro-notas/curso/<int:curso_pk>/', views.docente_libro_de_notas_por_curso, name='docente_libro_de_notas_por_curso'),

    # Noticias y Anuncios
    path('noticias/', views.NoticiaListView.as_view(), name='lista_noticias'),
    path('noticias/<int:pk>/', views.NoticiaDetailView.as_view(), name='detalle_noticia'),
    path('gestion/noticias/', views.NoticiaGestionListView.as_view(), name='lista_noticias_gestion'),
    path('gestion/noticias/crear/', views.NoticiaCreateView.as_view(), name='crear_noticia'),
    path('gestion/noticias/<int:pk>/editar/', views.NoticiaUpdateView.as_view(), name='editar_noticia'),
    path('gestion/noticias/<int:pk>/eliminar/', views.NoticiaDeleteView.as_view(), name='eliminar_noticia'),
     # URL para Calendario Académico
    path('calendario/', views.calendario_academico_view, name='calendario_academico'),
    
    # URL para Ayuda y Soporte
    path('ayuda-soporte/', views.ayuda_soporte_view, name='ayuda_soporte'),
    path('cuentas-por-cobrar/', views.CuentaPorCobrarEstudianteListView.as_view(), name='lista_cuentas_por_cobrar'),
    path('cuentas-por-cobrar/crear/', views.CuentaPorCobrarEstudianteCreateView.as_view(), name='crear_cuenta_por_cobrar'),
    path('cuentas-por-cobrar/<int:pk>/editar/', views.CuentaPorCobrarEstudianteUpdateView.as_view(), name='editar_cuenta_por_cobrar'),
    path('cuentas-por-cobrar/<int:pk>/eliminar/', views.CuentaPorCobrarEstudianteDeleteView.as_view(), name='eliminar_cuenta_por_cobrar'),
    path('finanzas/mis-cuentas/', views.mis_cuentas, name='mis_cuentas'),
    path('finanzas/registrar-pago/<int:cuenta_id>/', views.registrar_pago, name='registrar_pago'),
    path('finanzas/editar-pago/<int:pago_id>/', views.editar_pago, name='editar_pago'),
    path('finanzas/eliminar-pago/<int:pago_id>/', views.eliminar_pago, name='eliminar_pago'),
    path('finanzas/recibo-pago/<int:pago_id>/', views.generar_recibo_pago, name='generar_recibo_pago'),
    path('finanzas/volante-matricula/<int:estudiante_id>/', views.generar_volante_matricula, name='volante_matricula'),

    
]


