from django.urls import path
from . import views

app_name = "elearning"

urlpatterns = [
    path("catalogo/", views.catalogo_cursos, name="catalogo"),
    path("detalle/<int:curso_id>/", views.detalle_curso, name="detalle_curso"),
    path("aula/<int:curso_id>/", views.aula_virtual, name="aula_virtual"),
    path("evaluacion/<int:modulo_id>/", views.rendir_evaluacion, name="rendir_evaluacion"),
    path("certificado/<int:curso_id>/", views.generar_certificado_pdf, name="generar_certificado"),
    path("gestion/", views.gestion_cursos_admin, name="gestion_cursos_admin"),
    path("crear/", views.crear_curso, name="crear_curso"),
    path("editar/<int:curso_id>/", views.editar_curso, name="editar_curso"),
    path("configurar/<int:curso_id>/", views.configurar_curso, name="configurar_curso"),
    path("modulo/agregar/<int:curso_id>/", views.agregar_modulo, name="agregar_modulo"),
    path("material/agregar/<int:modulo_id>/", views.agregar_material, name="agregar_material"),
    path("evaluacion/agregar/<int:modulo_id>/", views.agregar_evaluacion, name="agregar_evaluacion"),
    path("matricular/", views.matricular_estudiante_manual, name="matricular_manual"),
    path("admision-express/", views.registrar_estudiante_curso, name="registrar_estudiante_curso"),
    path("reportes/", views.reporte_estadisticas_cursos, name="reporte_estadisticas"),
    path("curso/<int:curso_id>/estudiantes/", views.lista_estudiantes_curso, name="lista_estudiantes_curso"),
]
