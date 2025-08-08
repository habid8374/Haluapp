import sys
import os
import django
from django.core.management import call_command

if __name__ == "__main__":
    # 1. Configura la variable de entorno para el archivo de settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proyecto_colegio.settings")

    # 2. Inicializa el entorno de Django
    django.setup()

    # 3. Reconfigura la codificación de la salida estándar
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

    # 4. Llama al comando dumpdata
    call_command("dumpdata",
                 "--natural-foreign",
                 "--natural-primary",
                 "--indent", "2",
                 "--exclude", "auth.permission",
                 "--exclude", "contenttypes",
                 stdout=sys.stdout)