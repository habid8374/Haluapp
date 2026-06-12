from django.urls import path
from . import views

app_name = "platform_control"

urlpatterns = [
    path("",                                    views.dashboard,                  name="dashboard"),
    path("login/",                              views.login_view,                 name="login"),
    path("lock/",                               views.lock_view,                  name="lock"),
    path("institucion/<int:pk>/toggle/",        views.toggle_institucion,         name="toggle_institucion"),
    path("soporte/",                            views.tickets_view,               name="tickets"),
    path("soporte/<str:ticket_id>/",            views.ticket_detail_view,         name="ticket_detail"),
    path("soporte/<str:ticket_id>/cerrar/",     views.cerrar_ticket_view,         name="cerrar_ticket"),
    path("mantenimiento/",                      views.mantenimiento_dashboard,    name="mantenimiento"),
    path("mantenimiento/ejecutar/",             views.mantenimiento_ejecutar,     name="mantenimiento_ejecutar"),
    path("mantenimiento/<int:pk>/",             views.mantenimiento_detalle,      name="mantenimiento_detalle"),
    path("mantenimiento/<int:pk>/estado/",      views.mantenimiento_estado_api,   name="mantenimiento_estado_api"),
    path("nuevo-colegio/",                       views.onboarding_nuevo_colegio,   name="onboarding_nuevo_colegio"),
]
