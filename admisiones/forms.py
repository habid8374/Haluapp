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
            'nombres', 'apellidos', 'numero_documento', 'tipo_documento',
            'fecha_nacimiento', 'lugar_nacimiento',
            'email_contacto', 'telefono_contacto', 'grado_aspira',
            'sexo', 'grupo_sanguineo', 'eps', 'discapacidad',
            'colegio_procedencia', 'municipio_ciudad', 'departamento',
            'direccion', 'requiere_pago_inscripcion',
            # ── Caracterización SIMAT/SIMPADE (Fase 2) ──
            'pais_origen', 'zona_residencia', 'regimen_salud',
            'discapacidad_categoria', 'capacidad_excepcional', 'grupo_etnico',
            'estrato', 'sisben_grupo', 'sisben_puntaje',
            'victima_conflicto', 'tipo_poblacion_victima',
            'srpa', 'apoyo_academico_especial',
        ]
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'lugar_nacimiento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Barranquilla, Atlántico'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono_contacto': forms.TextInput(attrs={'class': 'form-control'}),
            'grado_aspira': forms.Select(attrs={'class': 'form-select'}),
            'sexo': forms.Select(attrs={'class': 'form-select'}),
            'grupo_sanguineo': forms.Select(attrs={'class': 'form-select'}),
            'eps': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Sura, Nueva EPS, Coosalud…'}),
            'discapacidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco si no aplica'}),
            'colegio_procedencia': forms.TextInput(attrs={'class': 'form-control'}),
            'municipio_ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Calle, barrio, municipio'}),
            'requiere_pago_inscripcion': forms.CheckboxInput(attrs={'class': 'form-check-input ms-2'}),
            # ── Caracterización SIMAT/SIMPADE ──
            'pais_origen': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco si es Colombia'}),
            'zona_residencia': forms.Select(attrs={'class': 'form-select'}),
            'regimen_salud': forms.Select(attrs={'class': 'form-select'}),
            'discapacidad_categoria': forms.Select(attrs={'class': 'form-select'}),
            'capacidad_excepcional': forms.Select(attrs={'class': 'form-select'}),
            'grupo_etnico': forms.Select(attrs={'class': 'form-select'}),
            'estrato': forms.Select(attrs={'class': 'form-select'}),
            'sisben_grupo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: A1, B2, C3'}),
            'sisben_puntaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tipo_poblacion_victima': forms.Select(attrs={'class': 'form-select'}),
            'victima_conflicto': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'srpa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'apoyo_academico_especial': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'requiere_pago_inscripcion': '¿Generar cobro de inscripción para este aspirante?',
            'eps': 'EPS / Entidad de Salud',
            'grupo_sanguineo': 'Grupo Sanguíneo',
            'lugar_nacimiento': 'Lugar de Nacimiento',
        }
        help_texts = {
            'requiere_pago_inscripcion': 'Marque esta casilla si debe crearse una cuenta por cobrar para la inscripción.',
            'discapacidad': 'Opcional. Describe brevemente si el aspirante tiene alguna condición de salud o discapacidad.',
        }


class ImportarAspirantesForm(forms.Form):
    archivo_excel = forms.FileField(
        label="Selecciona un archivo Excel (.xlsx)",
        help_text=(
            "Usa la plantilla oficial. Columnas obligatorias: "
            "'nombres', 'apellidos', 'numero_documento', 'fecha_nacimiento' (AAAA-MM-DD o DD/MM/AAAA), "
            "'email_contacto', 'grado_aspira' (nombre exacto del grado), 'paga_inscripcion' (SI/NO). "
            "Columnas opcionales: 'tipo_documento' (TI/CC/RC/PA/CE/OT), 'lugar_nacimiento', "
            "'telefono_contacto', 'sexo' (M/F/O), 'grupo_sanguineo' (A+/O-/…), 'eps', "
            "'discapacidad', 'colegio_procedencia', 'municipio_ciudad', 'departamento', 'direccion'."
        ),
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx'}),
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Modo simulación (no crear registros, solo validar)",
        help_text="Recomendado en la primera carga: valida el archivo y muestra errores fila por fila sin crear aspirantes.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def clean_archivo_excel(self):
        archivo = self.cleaned_data['archivo_excel']
        max_bytes = 15 * 1024 * 1024  # 15 MB tope para el Excel
        if archivo.size > max_bytes:
            raise forms.ValidationError("El archivo supera el tamaño máximo permitido (15 MB).")
        nombre = (archivo.name or "").lower()
        if not nombre.endswith(".xlsx"):
            raise forms.ValidationError("Solo se aceptan archivos .xlsx (Excel moderno).")
        return archivo
