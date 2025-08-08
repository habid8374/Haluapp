# proyecto_colegio/__init__.py

# Esto asegurará que la app de Celery siempre se importe cuando
# Django se inicie. De esta forma, las tareas compartidas (@shared_task)
# serán descubiertas y registradas por todos los procesos.
from .celery import app as celery_app

__all__ = ('celery_app',)
