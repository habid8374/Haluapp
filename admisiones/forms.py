# admisiones/forms.py (Versión Corregida)

from django import forms
from .models import Aspirante
from gestion_academica.models import Grado

class AspiranteForm(forms.ModelForm):
    
    def __init__(self, *args, **kwargs):
        # Sacamos el 'user' que pasaremos desde la vista para filtrar
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs)
        
        # Si el usuario no es superadmin, filtramos el queryset de grados
        if user and not user.is_superuser:
            institucion = user.institucion_asociada
            if institucion:
                self.fields['grado_aspira'].queryset = Grado.objects.filter(institucion=institucion)

    class Meta:
        model = Aspirante
        fields = [
            'nombres', 'apellidos', 'numero_documento', 'fecha_nacimiento', 
            'email_contacto', 'grado_aspira',
            'sexo',
            'colegio_procedencia', 
            'municipio_ciudad',
            'departamento',
            'requiere_pago_inscripcion'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}),
            'grado_aspira': forms.Select(attrs={'class': 'form-select'}),
            'sexo': forms.Select(attrs={'class': 'form-select'}),
            'colegio_procedencia': forms.TextInput(attrs={'class': 'form-control'}),
            'municipio_ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'requiere_pago_inscripcion': forms.CheckboxInput(attrs={'class': 'form-check-input ms-2'}),
        }
        labels = {
            'requiere_pago_inscripcion': '¿Generar cobro de inscripción para este aspirante?'
        }
        help_texts = {
            'requiere_pago_inscripcion': 'Marque esta casilla si debe crearse una cuenta por cobrar para la inscripción.'
        }


class ImportarAspirantesForm(forms.Form):
    archivo_excel = forms.FileField(
        label="Selecciona un archivo Excel (.xlsx)",
        help_text="El archivo debe tener las columnas: 'nombres', 'apellidos', 'numero_documento', "
                  "'fecha_nacimiento (AAAA-MM-DD)', 'email_contacto', 'grado_aspira_id', "
                  "'sexo (M/F/O)', 'colegio_procedencia', 'municipio_ciudad', 'departamento', 'paga_inscripcion (SI/NO)'.",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'})
    )
