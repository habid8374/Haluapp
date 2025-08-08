from django.urls import path
from . import views

app_name = 'cuestionarios'

urlpatterns = [
    path('', views.CuestionarioListView.as_view(), name='lista'),
    path('editor/<int:actividad_pk>/', views.EditorCuestionarioView.as_view(), name='editor_cuestionario'),
    path('api/<int:actividad_pk>/', views.CuestionarioAPIView.as_view(), name='api_cuestionario'),
    path('toggle-activo/<int:cuestionario_id>/', views.ToggleCuestionarioActivoView.as_view(), name='toggle_activo'),
    path('resolver/<int:actividad_pk>/iniciar/', views.IniciarCuestionarioView.as_view(), name='iniciar_cuestionario'),
    path('resolver/intento/<int:intento_pk>/', views.ResolverCuestionarioView.as_view(), name='resolver_cuestionario'),
    path('resolver/api/<int:intento_pk>/', views.ResolverCuestionarioAPIView.as_view(), name='resolver_api'),
    path('intento/<int:intento_pk>/habilitar-extra/', views.HabilitarIntentoExtraView.as_view(), name='habilitar_intento_extra'),
    path('intento/<int:intento_pk>/revisar/', views.RevisarIntentoView.as_view(), name='revisar_intento'),
    path('intento/<int:intento_pk>/eliminar/', views.EliminarIntentoView.as_view(), name='eliminar_intento'),
    path('api/generar-preguntas/<int:cuestionario_pk>/', views.GenerarPreguntasIAView.as_view(), name='generar_preguntas_ia'),
    path('api/sugerir-calificacion/<int:respuesta_pk>/', views.SugerirCalificacionIAView.as_view(), name='sugerir_calificacion_ia'),
]
