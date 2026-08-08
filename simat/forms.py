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
