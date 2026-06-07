# proyecto_colegio/celery.py

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_colegio.settings')

# Le decimos explícitamente a Celery en qué aplicaciones debe buscar tareas.
# Esto es más robusto que el autodiscover puro.
app = Celery('proyecto_colegio', include=[
    'gestion_academica.tasks',
    'admisiones.tasks',
    'finanzas.tasks',
])

# Le decimos a Celery que cargue su configuración desde el settings.py de Django.
app.config_from_object('django.conf:settings', namespace='CELERY')

# La autodescubierta se puede mantener como respaldo, pero el 'include' ya hace el trabajo.
app.autodiscover_tasks()
