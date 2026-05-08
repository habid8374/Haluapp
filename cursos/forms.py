from django import forms
from .models import Curso, Modulo, Material, Evaluacion, Pregunta, Opcion
from finanzas.models import InstitucionEducativa

class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['institucion', 'nombre', 'descripcion', 'imagen_portada', 'duracion_horas', 'publicado']
        widgets = {
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'duracion_horas': forms.NumberInput(attrs={'class': 'form-control'}),
            'imagen_portada': forms.FileInput(attrs={'class': 'form-control'}),
            'publicado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario no es superadmin, quitamos el campo institución para que se asigne automática
        if self.user and not self.user.is_superuser:
            if 'institucion' in self.fields:
                del self.fields['institucion']

class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ['titulo', 'descripcion', 'orden']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['titulo', 'tipo', 'archivo', 'enlace', 'orden']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'enlace': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/...'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class EvaluacionForm(forms.ModelForm):
    class Meta:
        model = Evaluacion
        fields = ['titulo', 'porcentaje_aprobacion', 'intentos_permitidos']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'porcentaje_aprobacion': forms.NumberInput(attrs={'class': 'form-control'}),
            'intentos_permitidos': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class PreguntaForm(forms.ModelForm):
    class Meta:
        model = Pregunta
        fields = ['texto', 'puntos']
        widgets = {
            'texto': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'puntos': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class OpcionForm(forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ['texto', 'es_correcta']
        widgets = {
            'texto': forms.TextInput(attrs={'class': 'form-control'}),
            'es_correcta': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
