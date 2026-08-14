"""
Widgets del SIMAT.

`MunicipioSelect` etiqueta cada opción de municipio con `data-departamento`
(el id del departamento al que pertenece) para que el navegador pueda mostrar
solo los municipios del departamento elegido. `aplicar_cascada_depto_municipio`
conecta cada par departamento↔municipio de un formulario sin duplicar lógica.
"""
from django import forms

from .models import Municipio

# Pares (campo_departamento, campo_municipio) que existen en las fichas SIMAT.
# El nombre del municipio se obtiene reemplazando "departamento"→"municipio",
# así que el JS puede emparejarlos por nombre sin importar el prefijo del form.
PARES_DEPTO_MUNICIPIO = [
    ('lugar_expedicion_departamento', 'lugar_expedicion_municipio'),
    ('departamento_nacimiento', 'municipio_nacimiento'),
    ('departamento_residencia', 'municipio_residencia'),
]


class MunicipioSelect(forms.Select):
    """Select de municipio que agrega `data-departamento` a cada opción para
    filtrar en el navegador según el departamento seleccionado."""

    _mapa_depto = None

    @classmethod
    def _mapa(cls):
        # id_municipio → id_departamento (una sola consulta, cacheada por proceso).
        if cls._mapa_depto is None:
            cls._mapa_depto = dict(
                Municipio.objects.values_list('pk', 'departamento_id')
            )
        return cls._mapa_depto

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        pk = getattr(value, 'value', value)  # ModelChoiceIteratorValue → pk
        try:
            depto = self._mapa().get(int(pk))
        except (TypeError, ValueError):
            depto = None
        if depto is not None:
            option['attrs']['data-departamento'] = str(depto)
        return option


def aplicar_cascada_depto_municipio(form):
    """Marca los selects de departamento y reemplaza los de municipio por
    `MunicipioSelect` para habilitar el filtrado en cascada. Conserva el
    queryset/opciones del campo. Llamar al final del __init__ del formulario."""
    for depto_f, muni_f in PARES_DEPTO_MUNICIPIO:
        if depto_f in form.fields:
            w = form.fields[depto_f].widget
            css = (w.attrs.get('class', '') + ' js-depto-filtro').strip()
            w.attrs['class'] = css
        if muni_f in form.fields:
            fld = form.fields[muni_f]
            nuevo = MunicipioSelect(attrs={'class': 'form-select js-municipio-dependiente'})
            nuevo.choices = fld.choices  # preserva las opciones del ModelChoiceField
            fld.widget = nuevo
