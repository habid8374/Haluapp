from django import forms
from django.utils.html import escape
from django.utils.safestring import mark_safe


class CategoriaCPCWidget(forms.HiddenInput):
    """Buscador de Categoría CPC (~9.933 códigos del DANE) — un <select> plano
    sería inmanejable, así que se busca por texto contra
    `presupuesto:buscar_categoria_cpc` (JSON) y el id elegido se guarda en el
    input oculto real. El JS que hace la búsqueda vive en form_generico.html
    (se activa solo si encuentra `.cpc-buscador` en la página)."""

    def render(self, name, value, attrs=None, renderer=None):
        hidden_html = super().render(name, value, attrs, renderer)
        widget_id = (attrs or {}).get('id', f'id_{name}')
        inicial_label = ''
        if value:
            from .models import CategoriaCPC
            cat = CategoriaCPC.objects.filter(pk=value).first()
            if cat:
                inicial_label = f"{cat.codigo} · {cat.titulo}"
        return mark_safe(
            f'<div class="cpc-buscador" data-hidden-id="{widget_id}" style="position:relative;">'
            f'{hidden_html}'
            f'<input type="text" class="form-control cpc-buscador-input" autocomplete="off" '
            f'placeholder="Escribe para buscar (ej. computador, papelería, transporte)…" '
            f'value="{escape(inicial_label)}">'
            f'<div class="list-group cpc-buscador-resultados" '
            f'style="position:absolute;left:0;right:0;z-index:1000;max-height:260px;overflow-y:auto;display:none;"></div>'
            f'</div>'
        )
