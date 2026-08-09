from django.urls import path
from . import views

app_name = "platform_control"

urlpatterns = [
    path("",                                    views.dashboard,                  name="dashboard"),
    path("login/",                              views.login_view,                 name="login"),
    path("verificar-2fa/",                      views.verificar_2fa_superadmin,   name="verificar_2fa"),
    path("lock/",                               views.lock_view,                  name="lock"),
    path("institucion/<int:pk>/toggle/",        views.toggle_institucion,         name="toggle_institucion"),
    path("consumo-ia/",                         views.consumo_ia_global,          name="consumo_ia"),
    path("soporte/",                            views.tickets_view,               name="tickets"),
    path("soporte/<str:ticket_id>/",            views.ticket_detail_view,         name="ticket_detail"),
    path("soporte/<str:ticket_id>/cerrar/",     views.cerrar_ticket_view,         name="cerrar_ticket"),
    path("mantenimiento/",                      views.mantenimiento_dashboard,    name="mantenimiento"),
    path("mantenimiento/ejecutar/",             views.mantenimiento_ejecutar,     name="mantenimiento_ejecutar"),
    path("mantenimiento/<int:pk>/",             views.mantenimiento_detalle,      name="mantenimiento_detalle"),
    path("mantenimiento/<int:pk>/estado/",      views.mantenimiento_estado_api,   name="mantenimiento_estado_api"),
    path("nuevo-colegio/",                       views.onboarding_nuevo_colegio,   name="onboarding_nuevo_colegio"),
    path("backups/",                             views.backup_view,                name="backup"),
    path("backups/ejecutar/",                    views.backup_ejecutar,            name="backup_ejecutar"),
    path("conexiones/",                          views.conexiones_view,            name="conexiones"),
    path("conexiones/cerrar-sesion/",            views.cerrar_sesion_remota,       name="cerrar_sesion_remota"),
    path("conexiones/<int:user_id>/cerrar-todas/", views.cerrar_sesiones_usuario,  name="cerrar_sesiones_usuario"),
    path("conexiones/<int:user_id>/reset-emergencia/", views.restablecer_password_emergencia, name="reset_emergencia"),
]
