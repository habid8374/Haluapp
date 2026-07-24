"""
Reorganiza el índice del panel de administración de Django en categorías
temáticas, para que las ~25 apps del proyecto no aparezcan como cajas
sueltas y desordenadas (una por cada app instalada, orden alfabético plano).

No cambia ningún registro de modelo ni ningún `admin.py` existente — solo
reagrupa visualmente lo que Django ya construyó, igual que el menú
"Recursos Interactivos" del frontend agrupa crucigramas/sopa de
letras/memoria/etc. en un solo lugar para el usuario final.

Cómo funciona: se sobreescribe `AdminSite.get_app_list` (el método que arma
la lista de cajas del índice) para, después de que Django construya la lista
normal, fusionar los `app_label` de `CATEGORIAS` en una sola caja por
categoría. Las apps que no aparecen en `CATEGORIAS` (Django, allauth,
Celery, etc.) se muestran tal cual, después de las categorías.

Para agregar una app nueva a una categoría existente, solo hay que añadir su
`app_label` a la lista correspondiente aquí — no hace falta tocar ningún
`admin.py`.
"""
from django.contrib import admin
from django.urls import reverse

CATEGORIAS = [
    ("Gestión Académica", [
        'gestion_academica', 'cuestionarios', 'piar', 'simulacros',
        'autoevaluacion_institucional', 'evaluacion_docente',
    ]),
    ("Finanzas y Facturación", ['finanzas', 'facturacion_electronica']),
    ("Admisiones", ['admisiones']),
    ("Recursos Interactivos (Juegos)", [
        'crucigramas', 'sopa_letras', 'memoria', 'flashcards',
        'quiz_audio', 'secuencias', 'trazado', 'rompecabezas',
    ]),
    ("E-learning", ['elearning']),
    ("Comunicación", ['mensajeria']),
    ("Recursos Educativos 3D", ['recursos_educativos']),
    ("Seguridad y Auditoría", ['auditoria', 'passkeys', 'autenticacion_2fa']),
]

_get_app_list_original = admin.AdminSite.get_app_list


def _get_app_list_agrupado(self, request, app_label=None):
    app_list = _get_app_list_original(self, request, app_label=app_label)
    if app_label:
        # Vista de una sola app (ej. /admin/finanzas/) — se deja intacta.
        return app_list

    por_label = {app['app_label']: app for app in app_list}
    usados = set()
    categorias = []

    for nombre_categoria, app_labels in CATEGORIAS:
        modelos = []
        for label in app_labels:
            app = por_label.get(label)
            if not app:
                continue
            usados.add(label)
            modelos.extend(app['models'])
        if not modelos:
            continue
        modelos.sort(key=lambda m: m['name'])
        categorias.append({
            'name': nombre_categoria,
            'app_label': nombre_categoria.lower().replace(' ', '_'),
            # No hay una URL de "índice de categoría" real (es una agrupación
            # virtual) — el encabezado enlaza de vuelta al índice del admin
            # en vez de dejar un href roto.
            'app_url': reverse('admin:index'),
            'has_module_perms': True,
            'models': modelos,
        })

    restantes = [app for app in app_list if app['app_label'] not in usados]
    return categorias + restantes


def instalar():
    admin.AdminSite.get_app_list = _get_app_list_agrupado
