from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Sede


class SedeForm(forms.ModelForm):
    """Alta/edición de una sede. La institución la fija la vista (multi-tenant)."""

    class Meta:
        model = Sede
        fields = [
            'nombre', 'codigo_dane_sede', 'consecutivo', 'zona',
            'jornada_principal', 'es_principal', 'activa',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Ej: Sede Principal, Sede San José…')}),
            'codigo_dane_sede': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Código DANE de 12 dígitos')}),
            'consecutivo': forms.TextInput(attrs={'class': 'form-control'}),
            'zona': forms.Select(attrs={'class': 'form-select'}),
            'jornada_principal': forms.Select(attrs={'class': 'form-select'}),
            'es_principal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': _('Nombre de la sede'),
            'codigo_dane_sede': _('Código DANE de la sede'),
            'consecutivo': _('Consecutivo (SIMAT)'),
            'zona': _('Zona'),
            'jornada_principal': _('Jornada principal'),
            'es_principal': _('¿Sede principal?'),
            'activa': _('Activa'),
        }


class GrupoForm(forms.ModelForm):
    """Alta/edición de un grupo/sección. La institución la fija la vista.

    Los desplegables de grado y sede se filtran a la institución (multi-tenant).
    """

    def __init__(self, *args, institucion=None, **kwargs):
        super().__init__(*args, **kwargs)
        from gestion_academica.models import Grado
        if institucion is not None:
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion).order_by('orden', 'nombre')
            self.fields['sede'].queryset = Sede.objects.filter(institucion=institucion, activa=True).order_by('-es_principal', 'nombre')
        self.fields['sede'].required = False
        self.fields['jornada'].required = False

    class Meta:
        from gestion_academica.models import Grupo
        model = Grupo
        fields = ['grado', 'nombre', 'sede', 'jornada', 'activo']
        widgets = {
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Ej: 01, 02, A, B…')}),
            'sede': forms.Select(attrs={'class': 'form-select'}),
            'jornada': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'grado': _('Grado'),
            'nombre': _('Nombre del grupo'),
            'sede': _('Sede'),
            'jornada': _('Jornada'),
            'activo': _('Activo'),
        }
