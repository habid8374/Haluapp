from django import forms
from django.utils.translation import gettext_lazy as _

from gestion_academica.models import ActividadCalificable, Curso, DBAPredefinido

# Debe coincidir con halu_math.views.GRADOS_PILOTO — el piloto de Halu Math
# solo cubre Matemáticas, grados 3°-5°.
GRADOS_PILOTO = ['3', '4', '5']


class _DBAChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, dba):
        texto = dba.enunciado if len(dba.enunciado) <= 110 else dba.enunciado[:110] + '…'
        return f"{dba.get_grado_display()} — DBA #{dba.numero}: {texto}"


class ActividadHaluMathForm(forms.ModelForm):
    """Crea una ActividadCalificable a partir de un conjunto de DBA de
    Halu Math. No pide 'tipo_actividad' — la vista resuelve sola la
    categoría 'Halu Math' (mismo patrón que la categoría 'Tareas' al
    calificar un Deber)."""

    dbas = _DBAChoiceField(
        queryset=DBAPredefinido.objects.filter(area='matematicas', grado__in=GRADOS_PILOTO).order_by('grado', 'numero'),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label=_("DBA a dominar"),
        help_text=_("El estudiante debe alcanzar el nivel Alto o dominar cada DBA elegido para obtener la nota máxima."),
    )

    class Meta:
        model = ActividadCalificable
        fields = ['curso', 'titulo', 'descripcion', 'fecha_publicacion', 'fecha_entrega_limite']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_publicacion': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_entrega_limite': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
        help_texts = {
            'fecha_entrega_limite': _(
                "Opcional. Después de esta fecha la nota deja de actualizarse sola — solo cambia con el botón "
                "«Recalcular notas ahora» o editándola a mano."
            ),
        }

    def __init__(self, *args, institucion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.filter(
            institucion=institucion, materia__nombre_materia__icontains='matemát',
        ).select_related('materia', 'grado', 'periodo_academico').order_by('grado__nombre', 'periodo_academico__nombre')
        self.fields['curso'].label = _("Curso (Matemáticas)")
