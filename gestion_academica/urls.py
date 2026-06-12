# gestion_academica/urls.py
from django.urls import path, include, reverse_lazy
from django.contrib import admin
from . import views
from django.views.generic import RedirectView
from gestion_academica.views import registro_inicial 
from django.conf.urls.static import static
from django.conf import settings
from rest_framework.authtoken import views as authtoken_views
from gestion_academica import views
from .views import guardar_layout_dashboard



admin.site.site_url = reverse_lazy('gestion_academica:inicio_academico')


app_name = 'gestion_academica'

urlpatterns = [
    
    path('registro_inicial/', registro_inicial, name='registro_inicial'),

    # Redirección para el login (generalmente gestionado en el urls.py principal o directamente por allauth/django.contrib.auth)
    # Si 'accounts/login/' es la URL principal de login, esto es redundante si ya está en el urls.py principal.
    # Si quieres que /gestion_academica/login/ redirija, esto es correcto.
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False)), 

    # Inicio del Módulo Académico
    path('', views.inicio_academico, name='inicio_academico'),

    # --- Gestión de Grados ---
    path('grados/', views.GradoListView.as_view(), name='lista_grados'),
    path('grados/crear/', views.GradoCreateView.as_view(), name='crear_grado'),
    path('grados/<int:pk>/editar/', views.GradoUpdateView.as_view(), name='editar_grado'),
    path('grados/<int:pk>/eliminar/', views.GradoDeleteView.as_view(), name='eliminar_grado'),

    # --- Gestión de Estudiantes ---
    path('estudiantes/', views.GradoParaEstudiantesListView.as_view(), name='lista_grados_para_estudiantes'),
    path('estudiantes/grado/<int:grado_pk>/', views.EstudiantesPorGradoListView.as_view(), name='lista_estudiantes_por_grado'),
    path('estudiantes/crear/', views.crear_estudiante, name='crear_estudiante'),
    path('estudiantes/<int:pk>/', views.EstudianteDetailView.as_view(), name='detalle_estudiante'),
    path('estudiantes/<int:pk>/editar/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiantes/<int:pk>/eliminar/', views.EstudianteDeleteView.as_view(), name='eliminar_estudiante'),

    # --- Gestión de Docentes ---
    path('docentes/', views.DocenteListView.as_view(), name='lista_docentes'),
    path('docentes/crear/', views.crear_docente, name='crear_docente'),
    path('docentes/<int:pk>/', views.DocenteDetailView.as_view(), name='detalle_docente'),
    path('docentes/<int:pk>/editar/', views.editar_docente, name='editar_docente'),
    path('docentes/<int:pk>/eliminar/', views.DocenteDeleteView.as_view(), name='eliminar_docente'),
    path('docente/gestion/', views.CentroGestionDocenteView.as_view(), name='centro_gestion_docente'),
    path('docente/reportes/hub/', views.docente_hub_reportes, name='docente_hub_reportes'),
    path('docentes/importar-excel/', views.importar_docentes_excel, name='importar_docentes_excel'),
    path('docentes/descargar-plantilla/', views.descargar_plantilla_docentes, name='descargar_plantilla_docentes'),
    path('docentes/<int:pk>/carnet/', views.generar_carnet_docente, name='generar_carnet_docente'),
    path('asistencia-docente/escaner/', views.escaner_asistencia_docente, name='escaner_asistencia_docente'),
    path('asistencia-docente/api/', views.registrar_asistencia_docente_api, name='registrar_asistencia_docente_api'),
    path('asistencia-docente/historial/', views.RegistroAsistenciaDocenteListView.as_view(), name='historial_asistencia_docente'),
    path('asistencias/hoy/', views.asistencias_docentes_hoy_api, name='asistencias_docentes_hoy_api'),
    path('asistencias/docentes/exportar/', views.exportar_asistencia_docentes_excel, name='exportar_asistencia_docentes_excel'),
    path('asistencias-docente/', views.ListaAsistenciasDocenteView.as_view(), name='lista_asistencias_docente'),

    path('docente/gestion/materiales/', views.DocenteMaterialListView.as_view(), name='docente_lista_materiales'),
    path('docente/gestion/materiales/subir/', views.DocenteMaterialCreateView.as_view(), name='docente_crear_material'),
    path('docente/gestion/materiales/<int:pk>/editar/', views.DocenteMaterialUpdateView.as_view(), name='docente_editar_material'),
    path('docente/gestion/materiales/<int:pk>/eliminar/', views.DocenteMaterialDeleteView.as_view(), name='docente_eliminar_material'),

    # --- Gestión de Materias ---
    path('materias/', views.MateriaListView.as_view(), name='lista_materias'),
    path('materias/crear/', views.MateriaCreateView.as_view(), name='crear_materia'),
    path('materias/<int:pk>/editar/', views.MateriaUpdateView.as_view(), name='editar_materia'),
    path('materias/<int:pk>/eliminar/', views.MateriaDeleteView.as_view(), name='eliminar_materia'),

    # --- Gestión de Periodos Académicos ---
    path('periodos/', views.PeriodoAcademicoListView.as_view(), name='lista_periodos'),
    path('periodos/crear/', views.PeriodoAcademicoCreateView.as_view(), name='crear_periodo'),
    path('periodos/<int:pk>/editar/', views.PeriodoAcademicoUpdateView.as_view(), name='editar_periodo'),
    path('periodos/<int:pk>/eliminar/', views.PeriodoAcademicoDeleteView.as_view(), name='eliminar_periodo'),
    path('proceso-graduacion/', views.proceso_graduacion_view, name='proceso_graduacion'),
    path('portal-egresado/', views.portal_egresado_view, name='portal_egresado'), # ✅ AÑADE ESTA LÍNEA
    path('curso/<int:curso_pk>/evaluar-logros/', views.evaluar_logros_curso, name='evaluar_logros_curso'),
    path('docente/logros/', views.LogroListView.as_view(), name='logro_lista'),
    path('docente/logros/crear/', views.LogroCreateView.as_view(), name='logro_crear'),
    path('docente/logros/<int:pk>/editar/', views.LogroUpdateView.as_view(), name='logro_editar'),
    path('docente/logros/<int:pk>/eliminar/', views.LogroDeleteView.as_view(), name='logro_eliminar'),
    

    # --- Gestión de Cursos ---
    path('cursos/', views.CursoListView.as_view(), name='lista_cursos'),
    path('cursos/crear/', views.CursoCreateView.as_view(), name='crear_curso'),
    path('cursos/<int:pk>/', views.CursoDetailView.as_view(), name='detalle_curso'),
    path('cursos/<int:pk>/editar/', views.CursoUpdateView.as_view(), name='editar_curso'),
    path('cursos/<int:pk>/eliminar/', views.CursoDeleteView.as_view(), name='eliminar_curso'),

    # --- Gestión de Directores de Curso ---
    path('directores-curso/', views.DirectorCursoListView.as_view(), name='lista_directores_curso'),
    path('directores-curso/asignar/', views.DirectorCursoCreateView.as_view(), name='crear_director_curso'),
    path('directores-curso/<int:pk>/editar/', views.DirectorCursoUpdateView.as_view(), name='editar_director_curso'),
    path('directores-curso/<int:pk>/eliminar/', views.DirectorCursoDeleteView.as_view(), name='eliminar_director_curso'),

    # --- Gestión de Esquemas de Calificación ---
    path('esquemas-calificacion/', views.EsquemaCalificacionListView.as_view(), name='lista_esquemas_calificacion'),
    path('esquemas-calificacion/crear/', views.EsquemaCalificacionCreateView.as_view(), name='crear_esquema_calificacion'),
    path('esquemas-calificacion/<int:pk>/editar/', views.EsquemaCalificacionUpdateView.as_view(), name='editar_esquema_calificacion'),
    path('esquemas-calificacion/<int:pk>/eliminar/', views.EsquemaCalificacionDeleteView.as_view(), name='eliminar_esquema_calificacion'),

    # --- Gestión de Tipos de Actividad ---
    path('tipos-actividad/', views.TipoActividadListView.as_view(), name='lista_tipos_actividad'),
    path('tipos-actividad/crear/', views.TipoActividadCreateView.as_view(), name='crear_tipo_actividad'),
    path('tipos-actividad/<int:pk>/editar/', views.TipoActividadUpdateView.as_view(), name='editar_tipo_actividad'),
    path('tipos-actividad/<int:pk>/eliminar/', views.TipoActividadDeleteView.as_view(), name='eliminar_tipo_actividad'),

    # --- Gestión de Actividades Calificables ---
    path('actividades/', views.ActividadCalificableListView.as_view(), name='lista_actividades_calificables'),
    path('actividades/crear/', views.ActividadCalificableCreateView.as_view(), name='crear_actividad_calificable'),
    path('actividades/<int:pk>/', views.ActividadCalificableDetailView.as_view(), name='detalle_actividad_calificable'),
    path('actividades/<int:pk>/editar/', views.ActividadCalificableUpdateView.as_view(), name='editar_actividad_calificable'),
    path('actividades/<int:pk>/eliminar/', views.ActividadCalificableDeleteView.as_view(), name='eliminar_actividad_calificable'),
    
    # --- Registro de Calificaciones (por Docentes) ---
    path('actividad/<int:actividad_pk>/calificar/', views.listar_estudiantes_para_calificar, name='listar_estudiantes_para_calificar'),
    path('actividad/<int:actividad_pk>/calificar/estudiante/<int:estudiante_pk>/', views.registrar_editar_calificacion, name='registrar_editar_calificacion'),

    # --- Gestión de Deberes / Tareas ---
    path('deberes/', views.DeberListView.as_view(), name='lista_deberes'),
    path('deberes/crear/', views.DeberCreateView.as_view(), name='crear_deber'),
    path('deberes/<int:pk>/', views.DeberDetailView.as_view(), name='detalle_deber'),
    path('deberes/<int:pk>/editar/', views.DeberUpdateView.as_view(), name='editar_deber'),
    path('deberes/<int:pk>/eliminar/', views.DeberDeleteView.as_view(), name='eliminar_deber'),

    # --- Gestión de Planes Curriculares ---
    path('planes-curriculares/', views.PlanCurricularListView.as_view(), name='lista_planes_curriculares'),
    path('planes-curriculares/crear/', views.PlanCurricularCreateView.as_view(), name='crear_plan_curricular'),
    path('planes-curriculares/<int:pk>/', views.PlanCurricularDetailView.as_view(), name='detalle_plan_curricular'),
    path('planes-curriculares/<int:pk>/editar/', views.PlanCurricularUpdateView.as_view(), name='editar_plan_curricular'),
    path('planes-curriculares/<int:pk>/eliminar/', views.PlanCurricularDeleteView.as_view(), name='eliminar_plan_curricular'),

    # --- Gestión de Menciones y Reconocimientos ---
    path('menciones/', views.MencionReconocimientoListView.as_view(), name='lista_menciones'),
    path('menciones/registrar/', views.MencionReconocimientoCreateView.as_view(), name='crear_mencion'),
    path('menciones/<int:pk>/editar/', views.MencionReconocimientoUpdateView.as_view(), name='editar_mencion'),
    path('menciones/<int:pk>/eliminar/', views.MencionReconocimientoDeleteView.as_view(), name='eliminar_mencion'),

    # --- Gestión de Archivos de Planes Académicos y Materiales ---
    path('archivos-planes/', views.ArchivoPlanAcademicoListView.as_view(), name='lista_archivos_plan'),
    path('archivos-planes/subir/', views.ArchivoPlanAcademicoCreateView.as_view(), name='crear_archivo_plan'),
    path('archivos-planes/<int:pk>/editar/', views.ArchivoPlanAcademicoUpdateView.as_view(), name='editar_archivo_plan'),
    path('archivos-planes/<int:pk>/eliminar/', views.ArchivoPlanAcademicoDeleteView.as_view(), name='eliminar_archivo_plan'),

    # --- Portal del Estudiante ---
    path('mis-calificaciones/', views.mis_cursos_y_calificaciones_resumen, name='mis_cursos_calificaciones'),
    path('mis-calificaciones/curso/<int:curso_pk>/', views.detalle_mis_calificaciones_por_curso, name='detalle_mis_calificaciones_por_curso'),
    path('mi-boletin/', views.mi_boletin_periodo_actual, name='mi_boletin_periodo_actual'),
    path('mis-deberes/', views.mis_deberes_lista, name='mis_deberes_lista'),
    path('deber/<int:deber_pk>/entregar/', views.realizar_entrega_deber, name='realizar_entrega_deber'),

    # --- Portal de Familiares ---
    path('portal-familiar/', views.portal_familiar_inicio, name='portal_familiar_inicio'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/calificaciones/', views.familiar_ver_calificaciones_estudiante, name='familiar_ver_calificaciones_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/calificaciones/curso/<int:curso_pk>/', views.familiar_ver_detalle_calificaciones_curso_estudiante, name='familiar_ver_detalle_calificaciones_curso_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/boletin/', views.familiar_ver_boletin_estudiante, name='familiar_ver_boletin_estudiante'),
    path('portal-familiar/estudiante/<int:estudiante_pk>/deberes/', views.familiar_ver_deberes_estudiante, name='familiar_ver_deberes_estudiante'),

    # --- Docentes - Libro de Notas ---
    path('libro-notas/seleccionar-curso/', views.docente_seleccionar_curso_libro_notas, name='docente_seleccionar_curso_libro_notas'),
    path('libro-notas/curso/<int:curso_pk>/', views.docente_libro_de_notas_por_curso, name='docente_libro_de_notas_por_curso'),
    # --- Coordinador - Libro de Notas (supervisión) ---
    path('coordinador/libro-notas/seleccionar-curso/', views.coordinador_seleccionar_curso_libro_notas, name='coordinador_seleccionar_curso_libro_notas'),
    path('lecciones/seleccionar-curso/', views.seleccionar_curso_para_leccion, name='seleccionar_curso_para_leccion'),
    path('lecciones/registrar/<int:curso_pk>/', views.registrar_leccion_diaria, name='registrar_leccion'),
    path('dashboard/', views.dashboard_docente, name='dashboard_docente'), 
    path('asistencia/seleccionar-curso/', views.seleccionar_curso_asistencia, name='seleccionar_curso_asistencia'),
    # --- Gestión de Descriptores por Docente ---
    path('docente/gestion/descriptores/', views.DocenteDescriptorListView.as_view(), name='docente_lista_descriptores'),
    path('docente/gestion/descriptores/crear/', views.DocenteDescriptorCreateView.as_view(), name='docente_crear_descriptor'),
    path('docente/gestion/descriptores/<int:pk>/editar/', views.DocenteDescriptorUpdateView.as_view(), name='docente_editar_descriptor'),
    path('docente/gestion/descriptores/<int:pk>/eliminar/', views.DocenteDescriptorDeleteView.as_view(), name='docente_eliminar_descriptor'),
    # --- Gestión de Menciones por Docente ---
    path('docente/gestion/descriptores/descargar-plantilla/', views.descargar_plantilla_view, name='docente_descargar_plantilla'),
    path('docente/gestion/menciones/', views.DocenteMencionListView.as_view(), name='docente_lista_menciones'),
    path('docente/gestion/menciones/crear/', views.DocenteMencionCreateView.as_view(), name='docente_crear_mencion'),
    path('docente/gestion/menciones/<int:pk>/editar/', views.DocenteMencionUpdateView.as_view(), name='docente_editar_mencion'),
    path('docente/gestion/menciones/<int:pk>/eliminar/', views.DocenteMencionDeleteView.as_view(), name='docente_eliminar_mencion'),
    path('docente/gestion/menciones/<int:mencion_pk>/pdf/', views.generar_mencion_pdf, name='generar_mencion_pdf'),
    # --- Gestión del Observador por Docente ---
    path('docente/gestion/observador/', views.seleccionar_estudiante_observador, name='seleccionar_estudiante_observador'),
    path('docente/gestion/observador/<int:estudiante_pk>/', views.historial_observador_estudiante, name='historial_observador'),
    path('docente/gestion/observador/<int:estudiante_pk>/pdf/', views.exportar_observador_pdf, name='exportar_observador_pdf'),
    # --- Gestión de Actividades por Docente ---
    path('docente/gestion/actividades/', views.DocenteActividadListView.as_view(), name='docente_lista_actividades'),
    path('docente/gestion/actividades/crear/', views.DocenteActividadCreateView.as_view(), name='docente_crear_actividad'),
    path('docente/gestion/actividades/<int:pk>/editar/', views.DocenteActividadUpdateView.as_view(), name='docente_editar_actividad'),
    path('docente/gestion/actividades/<int:pk>/eliminar/', views.DocenteActividadDeleteView.as_view(), name='docente_eliminar_actividad'),
    path('docente/reporte-riesgo/', views.reporte_riesgo_academico_view, name='reporte_riesgo_academico'),
    path('docente/reporte-riesgo/exportar/', views.exportar_reporte_riesgo_view, name='exportar_reporte_riesgo'),
    path('docente/reporte-riesgo/<int:estudiante_pk>/', views.detalle_riesgo_estudiante_view, name='detalle_riesgo_estudiante'),
    path('docente/panel-director/exportar/', views.exportar_panel_director_excel, name='exportar_panel_director'),
    path('curso/<int:curso_pk>/gestion-cualitativa/', views.gestionar_curso_cualitativo, name='gestionar_curso_cualitativo'),

    # --- Reporte de Nota Mínima ---
    path('docente/gestion/reporte-nota-minima/', views.seleccionar_curso_reporte_nota_minima, name='seleccionar_curso_reporte_nota_minima'),
    path('docente/gestion/reporte-nota-minima/<int:curso_pk>/', views.generar_reporte_nota_minima, name='generar_reporte_nota_minima'),
    # --- URL para el Panel del Director de Grupo ---
    path('docente/gestion/panel-director/', views.panel_director_grupo, name='panel_director_grupo'),
    path('reportes/riesgo-global/', views.reporte_riesgo_global_view, name='reporte_riesgo_global'),

    # 2. Gestión de Categorías de Calificación (Tipos de Actividad)
    path('docente/gestion/categorias/', views.DocenteTipoActividadListView.as_view(), name='docente_lista_tipos_actividad'),
    path('docente/gestion/categorias/crear/', views.DocenteTipoActividadCreateView.as_view(), name='docente_crear_tipo_actividad'),
    path('docente/gestion/categorias/<int:pk>/editar/', views.DocenteTipoActividadUpdateView.as_view(), name='docente_editar_tipo_actividad'),
    path('docente/gestion/categorias/<int:pk>/eliminar/', views.DocenteTipoActividadDeleteView.as_view(), name='docente_eliminar_tipo_actividad'),
  
     
     # --- URLs para Noticias (Lado del Usuario) ---
    path('noticias/', views.NoticiaListView.as_view(), name='lista_noticias'),
    path('noticias/<int:pk>/', views.NoticiaDetailView.as_view(), name='detalle_noticia'),
    
    # --- URLs para Gestión de Noticias (para Admin/Docentes desde la App) ---
    path('gestion/noticias/', views.NoticiaGestionListView.as_view(), name='lista_noticias_gestion'),
    path('gestion/noticias/crear/', views.NoticiaCreateView.as_view(), name='crear_noticia'),
    path('gestion/noticias/<int:pk>/editar/', views.NoticiaUpdateView.as_view(), name='editar_noticia'),
    path('gestion/noticias/<int:pk>/eliminar/', views.NoticiaDeleteView.as_view(), name='eliminar_noticia'),

    # --- Otros ---
    path('calendario/', views.calendario_academico_view, name='calendario_academico'),
    path('ayuda-soporte/', views.ayuda_soporte_view, name='ayuda_soporte'),
    path('mi-boletin/', views.mi_boletin_periodo_actual, name='mi_boletin'),
    path('mi-boletin/imprimir/', views.boletin_imprimible, name='boletin_imprimible'),
    path('estudiantes/<int:estudiante_pk>/carnet/', views.generar_carnet_estudiante, name='generar_carnet_estudiante'),
    path('api/registrar-asistencia/', views.registrar_asistencia_api, name='registrar_asistencia_api'),
    path('areaacademica/', views.listar_areas_academicas, name='listar_areas_academicas'),
    path('areaacademica/add/', views.crear_area_academica, name='crear_area_academica'),
    path('areaacademica/<int:pk>/edit/', views.editar_area_academica, name='editar_area_academica'),
    path('areaacademica/<int:pk>/delete/', views.eliminar_area_academica, name='eliminar_area_academica'),
    path('asistencia/escaner/<int:curso_pk>/', views.escaner_asistencia, name='escaner_asistencia'),
    path('mi-perfil/', views.ver_mi_perfil, name='ver_mi_perfil'),
    path('dashboard/estudiante/', views.dashboard_estudiante, name='dashboard_estudiante'),
    path('api/calendario/eventos/', views.CalendarioEventosAPIView.as_view(), name='api_calendario_eventos'),
    path('boletin/imprimir/<int:estudiante_pk>/<int:periodo_pk>/', views.boletin_imprimible, name='boletin_imprimible'),  
    path('lecciones/seleccionar-curso/', views.seleccionar_curso_para_leccion, name='seleccionar_curso_para_leccion'),
    path('lecciones/registrar/<int:curso_pk>/', views.registrar_leccion_diaria, name='registrar_leccion'), 
    path('api/actividad/<int:pk>/', views.DetalleActividadAPIView.as_view(), name='api_detalle_actividad'),
    path('actividad/<int:actividad_pk>/resolver/', views.resolver_actividad_page, name='resolver_actividad'),   
    path('api/actividad/<int:actividad_pk>/enviar-respuestas/', views.EnviarRespuestasAPIView.as_view(), name='api_enviar_respuestas'), 
    path('docente/observaciones/<int:grado_pk>/<int:periodo_pk>/', views.gestionar_observaciones_curso, name='gestionar_observaciones'),
    path('docente/observaciones/formulario/<int:estudiante_pk>/<int:periodo_pk>/', views.gestionar_observacion_estudiante_form, name='gestionar_observacion_formulario'),
    path('leccion/<int:leccion_pk>/', views.detalle_leccion_diaria, name='detalle_leccion'),
    path('mis-calificaciones/materia/<int:materia_pk>/', views.detalle_calificaciones_por_materia, name='detalle_calificaciones_por_materia'),
    path('mi-historial-asistencia/', views.mi_historial_asistencia, name='mi_historial_asistencia'),
    path('asistencia/exportar/<int:curso_pk>/', views.exportar_asistencia_excel, name='exportar_asistencia_excel'),
    path('docente/gestion/reporte-nota-minima/<int:curso_pk>/exportar/', views.exportar_reporte_nota_minima_excel, name='exportar_reporte_nota_minima_excel'),
    path('docente/gestion/libro-notas/<int:curso_pk>/exportar/', views.exportar_libro_de_notas_excel, name='exportar_libro_de_notas_excel'),
    path('docente/gestion/tareas-por-calificar/', views.TareasPorCalificarView.as_view(), name='tareas_por_calificar'),
    path('docente/gestion/calificar-entrega/<int:pk>/', views.CalificarEntregaView.as_view(), name='calificar_entrega'), 
    path('reportes/riesgo-global/exportar/', views.exportar_reporte_riesgo_global_view, name='exportar_reporte_riesgo_global'),
    path('admin/asistencia-diaria/', views.asistencia_diaria_admin_view, name='admin_asistencia_diaria'), 
    path('api/asistencia-diaria-data/', views.asistencia_diaria_data_api, name='api_asistencia_diaria_data'),
    path('reportes/riesgo-academico/', views.dashboard_riesgo_academico, name='dashboard_riesgo_academico'),
    path('dashboard/coordinador/', views.dashboard_coordinador_view, name='dashboard_coordinador'),
    path('reportes/riesgo-global/', views.reporte_riesgo_global_view, name='reporte_riesgo_global'),
    path('reportes/riesgo/detalle/<int:estudiante_pk>/', views.detalle_riesgo_estudiante_view, name='detalle_riesgo_estudiante'),
    path('riesgo/citar-acudiente/<int:prediccion_pk>/', views.citar_acudiente_view, name='citar_acudiente'),
    path('riesgo/notificar-docente/<int:prediccion_pk>/', views.notificar_docente_view, name='notificar_docente'),
    path('riesgo/ejecutar-analisis/', views.ejecutar_analisis_riesgo_view, name='ejecutar_analisis_riesgo'),
    path('notificaciones/', views.lista_notificaciones_view, name='lista_notificaciones'),
    path('familiares/crear/', views.crear_familiar, name='crear_familiar'),
    path('familiares/cargar/', views.cargar_familiares, name='cargar_familiares'),
    path('familiares/plantilla/', views.descargar_plantilla_familiares, name='descargar_plantilla_familiares'),
    path('bienestar/alertas-sentimiento/', views.dashboard_bienestar_view, name='dashboard_bienestar'),
    path('bienestar/alerta/<int:pk>/', views.detalle_alerta_bienestar_view, name='detalle_alerta_bienestar'),
    path('docente/disponibilidad/', views.gestionar_disponibilidad_view, name='gestionar_disponibilidad'),
    path('docente/disponibilidad/eliminar/<int:pk>/', views.eliminar_disponibilidad_view, name='eliminar_disponibilidad'),
    path('citas/seleccionar-docente/', views.familiar_seleccionar_docente_cita, name='familiar_seleccionar_docente'),
    path('citas/agendar/<int:docente_pk>/', views.familiar_agendar_cita_view, name='familiar_agendar_cita'),
    path('docente/mis-citas/', views.mis_citas_view, name='docente_mis_citas'),
    path('docente/citas/gestionar/<int:pk>/', views.gestionar_cita_view, name='gestionar_cita'),
    path('coordinacion/supervisar-citas/', views.supervisar_citas_view, name='supervisar_citas'),
    path('coordinacion/cita/<int:pk>/', views.detalle_cita_supervision_view, name='detalle_cita_supervision'),
    path('certificados/seleccionar/', views.seleccionar_estudiante_certificado_view, name='seleccionar_estudiante_certificado'),
    path('certificados/generar/estudios/<int:estudiante_pk>/', views.generar_certificado_estudios_view, name='generar_certificado_estudios'),
    path('certificados/generar/matricula/<int:estudiante_pk>/', views.generar_constancia_matricula_view, name='generar_constancia_matricula'),
    path('certificados/generar/paz-y-salvo/<int:estudiante_pk>/', views.generar_paz_y_salvo_view, name='generar_paz_y_salvo'),
    path('promocion-anual/', views.promocion_anual_view, name='promocion_anual'),
    path('configuracion/promocion-grados/', views.gestionar_promocion_grados_view, name='gestionar_promocion_grados'),
    path('convivencia/historial/', views.historial_convivencia_view, name='historial_convivencia'),

    # --- Halu Sentinel: Ruta de Convivencia (Res. 1620) ---
    path('sentinel/casos/<int:pk>/', views.detalle_caso_convivencia, name='detalle_caso_convivencia'),
    path('sentinel/casos/abrir/<int:anotacion_pk>/', views.abrir_caso_manual, name='abrir_caso_manual'),
    path('sentinel/casos/<int:pk>/acta/', views.acta_caso_pdf, name='acta_caso_pdf'),
    path('elecciones/<int:eleccion_id>/analisis/', views.dashboard_eleccion_ia, name='dashboard_eleccion_ia'),
    path('elecciones/<int:eleccion_id>/acta/', views.acta_eleccion_view, name='acta_eleccion'),
    path('coordinacion/elecciones/', views.gestionar_elecciones_view, name='gestionar_elecciones'),
    path('actividad/<int:actividad_pk>/preguntas/', views.GestionarPreguntasActividadView.as_view(), name='gestionar_preguntas_actividad'),
    path('actividad/<int:actividad_pk>/preguntas/crear/', views.PreguntaCreateView.as_view(), name='crear_pregunta'),
    path('pregunta/<int:pk>/editar/', views.PreguntaUpdateView.as_view(), name='editar_pregunta'),
    path('pregunta/<int:pk>/eliminar/', views.PreguntaDeleteView.as_view(), name='eliminar_pregunta'),

    path('aulas/', views.AulaListView.as_view(), name='lista_aulas'),
    path('aulas/crear/', views.AulaCreateView.as_view(), name='crear_aula'),
    path('aulas/<int:pk>/editar/', views.AulaUpdateView.as_view(), name='editar_aula'),
    path('aulas/<int:pk>/eliminar/', views.AulaDeleteView.as_view(), name='eliminar_aula'),
     
     # --- INICIO: URLS PARA LA API MÓVIL (V1) ---
    path('api/v1/mi-perfil/', views.perfil_usuario_api_view, name='api_mi_perfil'),
    path('api/v1/mis-cursos/', views.mis_cursos_api_view, name='api_mis_cursos'),
    path('api/v1/dashboard-docente/', views.dashboard_docente_api_view, name='api_dashboard_docente'),
    path('api/v1/dashboard-estudiante/', views.dashboard_estudiante_api_view, name='api_dashboard_estudiante'),
    path('api/v1/dashboard-coordinador/', views.dashboard_coordinador_api_view, name='api_dashboard_coordinador'),
    path('api/v1/portal-familiar/', views.portal_familiar_api_view, name='api_portal_familiar'),
    path('api/v1/dashboard-admin/', views.dashboard_admin_api_view, name='api_dashboard_admin'),
    path('api/v1/docente/seleccionar-curso-calificaciones/', views.api_seleccionar_curso_calificaciones, name='api_seleccionar_curso_calificaciones'),
    path('api/v1/libro-notas/curso/<int:curso_pk>/', views.libro_notas_api_view, name='api_libro_notas'),
    path('api/v1/libro-notas/curso/<int:curso_pk>/guardar/', views.guardar_libro_notas_api_view, name='api_guardar_libro_notas'),
    path('api/v1/api-token-auth/', authtoken_views.obtain_auth_token, name='api_token_auth'),
    path('api/v1/estudiante/mis-deberes/', views.mis_deberes_api_view, name='api_mis_deberes'),
    path('api/v1/estudiante/mi-boletin/', views.mi_boletin_api_view, name='api_mi_boletin'),
    path('api/v1/estudiante/mis-asignaturas/', views.mis_asignaturas_api_view, name='api_mis_asignaturas'),
    path('api/v1/estudiante/mi-horario/', views.mi_horario_api_view, name='api_mi_horario'),
    path('api/v1/estudiante/mi-asistencia/', views.mi_historial_asistencia_api_view, name='api_mi_asistencia'),
    path('api/v1/estudiante/mi-estado-cartera/', views.mi_estado_cartera_api_view, name='api_mi_estado_cartera'),
    path('api/v1/noticias/', views.lista_noticias_api_view, name='api_lista_noticias'),
    path('api/v1/estudiante/mis-menciones/', views.mis_menciones_api_view, name='api_mis_menciones'),
    path('api/v1/docente/seleccionar-curso-asistencia/', views.api_seleccionar_curso_asistencia, name='api_seleccionar_curso_asistencia'),
    path('api/v1/docente/seleccionar-curso-libro-notas/', views.api_seleccionar_curso_libro_notas, name='api_seleccionar_curso_libro_notas'),
    path('api/v1/docente/lista-actividades/', views.api_docente_lista_actividades, name='api_docente_lista_actividades'),
    path('api/v1/docente/lista-categorias/', views.api_docente_lista_categorias, name='api_docente_lista_categorias'),
    path('api/v1/docente/lista-descriptores/', views.api_docente_lista_descriptores, name='api_docente_lista_descriptores'),
    path('api/v1/docente/lista-materiales/', views.api_docente_lista_materiales, name='api_docente_lista_materiales'),
    path('api/v1/docente/seleccionar-curso-leccion/', views.api_seleccionar_curso_leccion, name='api_seleccionar_curso_leccion'),
    path('api/v1/docente/seleccionar-estudiante-observador/', views.api_seleccionar_estudiante_observador, name='api_seleccionar_estudiante_observador'),
    path('api/v1/docente/disponibilidad/', views.api_gestionar_disponibilidad, name='api_gestionar_disponibilidad'),
    path('api/v1/docente/lista-menciones/', views.api_docente_lista_menciones, name='api_docente_lista_menciones'),
    path('api/v1/docente/seleccionar-curso-reporte-minima/', views.api_seleccionar_curso_reporte_minima, name='api_seleccionar_curso_reporte_minima'),
    path('api/v1/docente/panel-director/', views.api_panel_director_grupo, name='api_panel_director_grupo'),
    # --- FIN: URLS DE API PARA DOCENTE ---
    # 2. Endpoints para las acciones del Panel de Coordinación
    path('api/v1/coordinacion/asistencia-diaria/', views.api_admin_asistencia_diaria, name='api_admin_asistencia_diaria'),
    path('api/v1/coordinacion/alertas-bienestar/', views.api_dashboard_bienestar, name='api_dashboard_bienestar'),
    path('api/v1/coordinacion/supervisar-citas/', views.api_supervisar_citas, name='api_supervisar_citas'),
    # 2. Endpoints para las acciones específicas por estudiante
    path('api/v1/familiar/estudiante/<int:estudiante_pk>/calificaciones/', views.api_familiar_calificaciones_view, name='api_familiar_calificaciones'),
    path('api/v1/familiar/estudiante/<int:estudiante_pk>/boletin/', views.api_familiar_boletin_view, name='api_familiar_boletin'),
    path('api/v1/familiar/estudiante/<int:estudiante_pk>/deberes/', views.api_familiar_deberes_view, name='api_familiar_deberes'),
    # 3. Endpoints para acciones generales del familiar
    path('api/v1/familiar/seleccionar-docente-cita/', views.api_familiar_seleccionar_docente, name='api_familiar_seleccionar_docente'), 
    path('api/v1/noticias/<int:noticia_pk>/', views.detalle_noticia_api_view, name='api_detalle_noticia'),
    path('api/v1/ia/sugerir-nombre-idioma/', views.api_sugerir_nombre_idioma, name='api_sugerir_nombre_idioma'),
    path('api/v1/ia/sugerir-nombres-idioma-masivo/', views.api_sugerir_nombres_idioma_masivo, name='api_sugerir_nombres_idioma_masivo'),
    path('api/v1/ia/guardar-nombres-idioma-masivo/', views.api_guardar_nombres_idioma_masivo, name='api_guardar_nombres_idioma_masivo'),
    path('curso/<int:curso_pk>/calificar/', views.redirigir_a_libro_de_notas, name='redirigir_libro_notas'),

    path('dimensiones/', views.DimensionListView.as_view(), name='lista_dimensiones'),
    path('dimensiones/crear/', views.DimensionCreateView.as_view(), name='crear_dimension'),
    path('dimensiones/<int:pk>/editar/', views.DimensionUpdateView.as_view(), name='editar_dimension'),
    path('dimensiones/<int:pk>/eliminar/', views.DimensionDeleteView.as_view(), name='eliminar_dimension'),
    path('escala-cualitativa/', views.EscalaCualitativaListView.as_view(), name='lista_escala_cualitativa'),
    path('escala-cualitativa/crear/', views.EscalaCualitativaCreateView.as_view(), name='crear_escala_cualitativa'),
    path('escala-cualitativa/<int:pk>/editar/', views.EscalaCualitativaUpdateView.as_view(), name='editar_escala_cualitativa'),
    path('escala-cualitativa/<int:pk>/eliminar/', views.EscalaCualitativaDeleteView.as_view(), name='eliminar_escala_cualitativa'),
    path('logros/', views.LogroListView.as_view(), name='logro_lista'),
    path('logros/crear/', views.LogroCreateView.as_view(), name='logro_crear'),
    path('logros/<int:pk>/editar/', views.LogroUpdateView.as_view(), name='logro_editar'),
    path('logros/<int:pk>/eliminar/', views.LogroDeleteView.as_view(), name='logro_eliminar'),
    # --- Descriptores de Logro (coordinador) ---
    path('descriptores/', views.CoordinadorDescriptorListView.as_view(), name='coordinador_lista_descriptores'),
    path('descriptores/crear/', views.CoordinadorDescriptorCreateView.as_view(), name='coordinador_crear_descriptor'),
    path('descriptores/<int:pk>/editar/', views.CoordinadorDescriptorUpdateView.as_view(), name='coordinador_editar_descriptor'),
    path('descriptores/<int:pk>/eliminar/', views.CoordinadorDescriptorDeleteView.as_view(), name='coordinador_eliminar_descriptor'),
    path('boletin-descriptivo/<int:estudiante_pk>/<int:periodo_pk>/', views.boletin_descriptivo_preescolar_pdf, name='boletin_descriptivo_preescolar'),
    path('generar-boletin/<int:estudiante_pk>/<int:periodo_pk>/', views.generar_boletin_dispatcher, name='generar_boletin'),
  

    #Halu--api#
    path('api/asistente-halu/', views.asistente_halu_api, name='asistente_halu_api'),

    path('reportes/rendimiento-estudiante/', views.reporte_rendimiento_estudiante, name='reporte_rendimiento_estudiante'),
    path('reportes/dashboard/', views.reportes_dashboard, name='reportes_dashboard'),
    path('reportes/acumulado-periodo/', views.reporte_acumulado_periodo, name='reporte_acumulado_periodo'),
    path('reportes/promedio-general-grado/', views.reporte_promedio_general_grado, name='reporte_promedio_general_grado'),
    path('reportes/estudiante-dashboard/', views.reporte_estudiante_dashboard, name='reporte_estudiante_dashboard'),
    path('reportes/rendimiento-por-grado/', views.reporte_rendimiento_por_grado, name='reporte_rendimiento_por_grado'),
    path('reportes/promedio-por-area/', views.reporte_promedio_por_area, name='reporte_promedio_por_area'),
    path('reportes/informe-reprobacion/', views.reporte_final_reprobacion, name='reporte_reprobacion'),
    path('reportes/consolidado-materia/', views.reporte_consolidado_materia, name='reporte_consolidado_materia'),
    path('reportes/consolidado-areas/', views.reporte_consolidado_areas, name='reporte_consolidado_areas'),
    path('reportes/ranking-institucion/', views.reporte_ranking_institucion, name='reporte_ranking_institucion'),
    path('reportes/promedio-cualitativo/', views.reporte_promedio_cualitativo, name='reporte_promedio_cualitativo'),
    path('reportes/promedio-por-materia/', views.reporte_promedio_por_materia, name='reporte_promedio_por_materia'),
    path('reportes/cuadro-honor-grado/', views.cuadro_honor_grado, name='cuadro_honor_grado'),
    path('reportes/asistencia-diaria/', views.reporte_estadistica_asistencia_diaria, name='reporte_asistencia_diaria'),
    path('reportes/asistencia-materia/', views.reporte_asistencia_materia, name='reporte_asistencia_materia'),
    path('reportes/incidencias/', views.reporte_incidencias_estudiante, name='reporte_incidencias'),
    path('reportes/consolidado-convivencia/', views.reporte_consolidado_convivencia, name='reporte_consolidado_convivencia'),

    path('espera-activacion/', views.espera_activacion, name='espera_activacion'),
    path('ayuda-soporte/ticket/<str:ticket_id>/', views.ticket_detail_view, name='ticket_detail'),
    path('docente/planeador/', views.planeacion_clases_view, name='planeador_clases'),
    path('docente/planeador/<int:pk>/', views.planeacion_detalle_view, name='planeacion_detalle'),
    path('docente/planeador/<int:pk>/cancelar/', views.cancelar_generacion_planeacion, name='cancelar_generacion_planeacion'),
    path('api/planeacion/<int:pk>/status/', views.get_planeacion_status_api, name='api_get_planeacion_status'),
    path('docente/planeador/<int:pk>/pdf/', views.generar_planeacion_pdf, name='generar_planeacion_pdf'),
    path('docente/planeador/<int:pk>/anadir-lecciones/', views.anadir_planeacion_a_lecciones, name='anadir_planeacion_a_lecciones'),
    path('google-calendar/callback/', views.google_calendar_callback, name='google_calendar_callback'),
    path('horarios/gestion/', views.gestion_horarios_view, name='gestion_horarios'),
    path('docente/lecciones/seleccionar-curso/', views.seleccionar_curso_para_lecciones, name='seleccionar_curso_para_lecciones'),
    path('docente/curso/<int:curso_pk>/lecciones/', views.lista_lecciones_diarias, name='lista_lecciones_diarias'),
    path('leccion/ia/<int:leccion_pk>/', views.detalle_leccion, name='detalle_leccion_ia'),
    path('coordinacion/elecciones/<int:eleccion_id>/candidatos/', views.gestionar_candidatos_view, name='gestionar_candidatos'),
    path('elecciones/candidato/<int:candidato_id>/', views.detalle_candidato_view, name='detalle_candidato'),
    path('elecciones/<int:eleccion_id>/analizar-propuestas/', views.analizar_propuestas_ia_view, name='analizar_propuestas_ia'),
    path('elecciones/<int:eleccion_id>/votar/', views.votar_view, name='votar_eleccion'),
    path('usuarios/lista/', views.lista_usuarios_view, name='lista_usuarios'),
    path('usuarios/<int:user_pk>/editar/', views.editar_usuario_view, name='editar_usuario'),
    path('docente/curso/<int:curso_pk>/pasar-lista/', views.pasar_lista_view, name='pasar_lista'),
    path('api/cursos-por-grado/<int:grado_id>/', views.get_cursos_por_grado_partial, name='api_get_cursos_por_grado'),
    path('material-refuerzo/<int:actividad_pk>/', views.MaterialRefuerzoView.as_view(), name='ver_material_refuerzo'),
    path('docente/gestion/historial-entregas/', views.HistorialEntregasView.as_view(), name='historial_entregas'),
    path('admin/sincronizar-permisos/', views.SincronizarPermisosView.as_view(), name='sincronizar_permisos'),
    path('notificaciones/marcar-leida/', views.MarcarNotificacionLeidaView.as_view(), name='marcar_notificacion_leida'),
    path('admin/ejecutar-analisis-comportamiento/', views.EjecutarAnalisisComportamientoView.as_view(), name='ejecutar_analisis_comportamiento'),
    path('admin/analisis-status/', views.AnalisisStatusView.as_view(), name='analisis_status'),
    path('api/generar-resumen-estudiante/<int:estudiante_pk>/<int:periodo_pk>/', views.GenerarResumenEstudianteIAView.as_view(), name='generar_resumen_ia'),
    path('admin/optimizador-horarios/', views.OptimizadorHorariosView.as_view(), name='optimizador_horarios'),
    path('api/guardar-horario/', views.GuardarHorarioView.as_view(), name='guardar_horario'),
    path('api/cursos-por-institucion/<int:institucion_id>/', views.cursos_por_institucion_api, name='api_cursos_por_institucion'),
    path('api/generar-correo-acudiente/<int:estudiante_pk>/<int:periodo_pk>/', views.GenerarCorreoAcudienteIAView.as_view(), name='generar_correo_ia'),
    path('dashboard/guardar-layout/', guardar_layout_dashboard, name='guardar_layout_dashboard'),

    # ── Malla Curricular (Coordinador / Jefe de Área) ──────────────────────
    path('mallas/', views.malla_curricular_list, name='malla_curricular_list'),
    path('mallas/<int:pk>/', views.malla_curricular_detalle, name='malla_curricular_detalle'),
    path('mallas/<int:pk>/eliminar/', views.malla_curricular_delete, name='malla_curricular_delete'),
    path('mallas/<int:pk>/imprimir/', views.malla_curricular_imprimir, name='malla_curricular_imprimir'),
    # ── Malla Curricular (Vista Docente, sólo lectura) ────────────────────────
    path('docente/mallas/', views.malla_docente_consulta, name='malla_docente_consulta'),
    path('docente/mallas/<int:pk>/', views.malla_docente_detalle, name='malla_docente_detalle'),
    path('docente/mallas/<int:pk>/imprimir/', views.malla_curricular_imprimir, name='malla_docente_imprimir'),
    path('mallas/<int:pk>/item/add/', views.item_malla_add, name='item_malla_add'),
    path('mallas/item/<int:item_pk>/editar/', views.item_malla_edit, name='item_malla_edit'),
    path('mallas/item/<int:item_pk>/eliminar/', views.item_malla_delete, name='item_malla_delete'),
    path('api/dba/', views.dba_predefinido_api, name='dba_predefinido_api'),
    path('api/generar-indicadores/', views.generar_indicadores_ia, name='generar_indicadores_ia'),
    path('api/sugerir-distribucion/', views.sugerir_distribucion_ia, name='sugerir_distribucion_ia'),

    # ── Plan Semanal (Docente) ─────────────────────────────────────────────
    path('docente/planes-semanales/', views.mis_planes_semanales, name='mis_planes_semanales'),
    path('docente/planes-semanales/nuevo/', views.plan_semanal_crear, name='plan_semanal_crear'),
    path('docente/planes-semanales/<int:pk>/', views.plan_semanal_detalle, name='plan_semanal_detalle'),
    path('docente/planes-semanales/<int:pk>/item/add/', views.item_plan_add, name='item_plan_add'),
    path('docente/planes-semanales/<int:pk>/enviar/', views.plan_semanal_enviar, name='plan_semanal_enviar'),
    path('docente/planes-semanales/item/<int:item_pk>/eliminar/', views.item_plan_delete, name='item_plan_delete'),
    path('docente/planes-semanales/item/<int:item_pk>/editar/', views.item_plan_edit, name='item_plan_edit'),
    path('docente/planes-semanales/item/<int:item_pk>/crear-deber/', views.item_plan_crear_deber, name='item_plan_crear_deber'),
    path('docente/planes-semanales/item/<int:item_pk>/crear-actividad/', views.item_plan_crear_actividad, name='item_plan_crear_actividad'),

    # ── Supervisión Coordinador ────────────────────────────────────────────
    path('coordinador/planes-semanales/', views.supervisar_planes_semanales, name='supervisar_planes_semanales'),
    path('coordinador/planes-semanales/<int:pk>/revisar/', views.revisar_plan_semanal, name='revisar_plan_semanal'),

    # ── Corte Preventivo ───────────────────────────────────────────────────
    path('cortes-preventivos/', views.lista_cortes_preventivos, name='lista_cortes_preventivos'),
    path('cortes-preventivos/crear/', views.crear_corte_preventivo, name='crear_corte_preventivo'),
    path('cortes-preventivos/<int:pk>/', views.detalle_corte_preventivo, name='detalle_corte_preventivo'),
    path('cortes-preventivos/<int:pk>/calcular/', views.calcular_corte, name='calcular_corte'),
    path('cortes-preventivos/<int:pk>/publicar/', views.publicar_corte, name='publicar_corte'),
    path('cortes-preventivos/<int:pk>/archivar/', views.archivar_corte, name='archivar_corte'),
    path('cortes-preventivos/<int:pk>/eliminar/', views.eliminar_corte, name='eliminar_corte'),
    path('cortes-preventivos/<int:pk>/observacion/', views.guardar_observacion_corte, name='guardar_observacion_corte'),
    path('cortes-preventivos/<int:pk>/resultado/<int:resultado_pk>/observacion/', views.guardar_observacion_estudiante, name='guardar_observacion_estudiante'),
    path('cortes-preventivos/<int:pk>/detalle/<int:detalle_pk>/observacion/', views.guardar_observacion_materia, name='guardar_observacion_materia'),
    path('cortes-preventivos/<int:pk>/notificar/', views.notificar_familias_corte, name='notificar_familias_corte'),
    path('cortes-preventivos/<int:pk>/pdf/grado/', views.exportar_pdf_grado, name='exportar_pdf_grado'),
    path('cortes-preventivos/<int:pk>/resultado/<int:resultado_pk>/pdf/', views.exportar_pdf_estudiante, name='exportar_pdf_estudiante'),
    path('cortes-preventivos/<int:pk>/excel/', views.exportar_excel_corte, name='exportar_excel_corte'),
    path('cortes-preventivos/configuracion/', views.configuracion_corte_preventivo, name='configuracion_corte_preventivo'),

]
    



# Configuración para servir archivos MEDIA en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)