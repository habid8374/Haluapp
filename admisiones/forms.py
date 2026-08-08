# admisiones/forms.py (Versión Corregida)

from django import forms
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, HTML
from .models import Aspirante
from gestion_academica.models import Grado
from simat.models import Sede

class AspiranteForm(forms.ModelForm):
    
    def __init__(self, *args, **kwargs):
        # Sacamos el 'user' que pasaremos desde la vista para filtrar
        user = kwargs.pop('user', None) 
        
        super().__init__(*args, **kwargs)

        # La fecha nativa (type=date) intercambia siempre en formato ISO.
        if 'fecha_nacimiento' in self.fields:
            self.fields['fecha_nacimiento'].input_formats = ['%Y-%m-%d', '%d/%m/%Y']

        # Si el usuario no es superadmin, filtramos por su institución
        institucion = None
        if user and not user.is_superuser:
            institucion = user.institucion_asociada
            if institucion:
                self.fields['grado_aspira'].queryset = Grado.objects.filter(institucion=institucion)
                self.fields['sede'].queryset = Sede.objects.filter(institucion=institucion, activa=True)
                if not self.instance.pk:
                    self.fields['sede'].initial = Sede.principal_de(institucion)

        # Grupo/sección como DESPLEGABLE (sin digitar) con los nombres de grupo
        # ya existentes en la institución; siempre incluye "01" por defecto.
        if 'grupo' in self.fields and institucion is not None:
            from gestion_academica.models import Grupo
            nombres = set(
                Grupo.objects.filter(institucion=institucion, activo=True)
                .values_list('nombre', flat=True)
            )
            nombres.add('01')
            choices = [('', '—')] + [(n, n) for n in sorted(nombres)]
            self.fields['grupo'].widget = forms.Select(attrs={'class': 'form-select'}, choices=choices)
            if not self.instance.pk and not (self.initial.get('grupo') or self.data.get('grupo')):
                self.fields['grupo'].initial = '01'

        # Las FK a catálogos SIMAT no son obligatorias
        for f in ['lugar_expedicion_departamento', 'lugar_expedicion_municipio',
                  'departamento_nacimiento', 'municipio_nacimiento',
                  'departamento_residencia', 'municipio_residencia',
                  'etnia_simat', 'resguardo', 'eps_simat', 'sede']:
            if f in self.fields:
                self.fields[f].required = False

        # Diseño en secciones profesionales (se renderiza con {% crispy form %})
        self.helper = FormHelper()
        self.helper.form_tag = False   # el <form> lo pone la plantilla
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Fieldset(
                _("1. Identificación"),
                'nombres', 'apellidos',
                'tipo_documento', 'numero_documento',
                'lugar_expedicion_departamento', 'lugar_expedicion_municipio',
                'fecha_nacimiento', 'sexo', 'grupo_sanguineo',
            ),
            Fieldset(
                _("2. Nacimiento y residencia"),
                'pais_origen', 'departamento_nacimiento', 'municipio_nacimiento',
                'departamento_residencia', 'municipio_residencia', 'barrio',
                'direccion', 'zona_residencia',
            ),
            Fieldset(
                _("3. Contacto"),
                'email_contacto', 'telefono_contacto',
            ),
            Fieldset(
                _("4. Caracterización socio-económica (SIMPADE)"),
                'estrato', 'sisben_grupo', 'sisben_puntaje', 'regimen_salud',
                'eps_simat',
                'discapacidad', 'discapacidad_categoria', 'capacidad_excepcional',
                'grupo_etnico', 'etnia_simat', 'resguardo',
                'victima_conflicto', 'tipo_poblacion_victima', 'srpa', 'campesino',
                'apoyo_academico_especial',
            ),
            Fieldset(
                _("5. Matrícula"),
                'grado_aspira', 'sede', 'jornada', 'grupo',
                'matricula_contratada', 'repitente',
                'colegio_procedencia', 'requiere_pago_inscripcion',
            ),
            Fieldset(
                _("6. Acudiente / Familiar"),
                'acudiente_nombres', 'acudiente_apellidos',
                'acudiente_tipo_documento', 'acudiente_documento',
                'acudiente_parentesco', 'acudiente_email', 'acudiente_telefono',
            ),
        )

    class Meta:
        model = Aspirante
        # CRITERIO ÚNICO (igual que la carga masiva): una sola representación por
        # concepto. El nombre va completo (se separa al guardar); ubicación/EPS
        # van por desplegable de catálogo y se derivan los textos internos.
        fields = [
            'nombres', 'apellidos', 'numero_documento', 'tipo_documento',
            'fecha_nacimiento',
            'email_contacto', 'telefono_contacto', 'grado_aspira',
            'sexo', 'grupo_sanguineo', 'discapacidad',
            'colegio_procedencia', 'direccion', 'requiere_pago_inscripcion',
            # ── Caracterización SIMPADE ──
            'pais_origen', 'zona_residencia', 'regimen_salud',
            'discapacidad_categoria', 'capacidad_excepcional', 'grupo_etnico',
            'estrato', 'sisben_grupo', 'sisben_puntaje',
            'victima_conflicto', 'tipo_poblacion_victima',
            'srpa', 'apoyo_academico_especial', 'campesino',
            # ── SIMAT: ubicación DANE, etnia/EPS por código y matrícula ──
            'lugar_expedicion_departamento', 'lugar_expedicion_municipio',
            'departamento_nacimiento', 'municipio_nacimiento',
            'departamento_residencia', 'municipio_residencia', 'barrio',
            'etnia_simat', 'resguardo', 'eps_simat',
            'sede', 'jornada', 'grupo', 'matricula_contratada', 'repitente',
            # ── Acudiente / Familiar (se crea/vincula al inscribir) ──
            'acudiente_nombres', 'acudiente_apellidos', 'acudiente_tipo_documento',
            'acudiente_documento', 'acudiente_parentesco', 'acudiente_email',
            'acudiente_telefono',
        ]
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control'}),
            'apellidos': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_documento': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
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
            'requiere_pago_inscripcion': _('¿Generar cobro de inscripción para este aspirante?'),
            'grupo_sanguineo': _('Grupo Sanguíneo'),
        }
        help_texts = {
            'requiere_pago_inscripcion': _('Marque esta casilla si debe crearse una cuenta por cobrar para la inscripción.'),
            'discapacidad': _('Opcional. Describe brevemente si el aspirante tiene alguna condición de salud o discapacidad.'),
        }

    def save(self, commit=True):
        """Deriva los campos internos desde la selección (sin duplicar columnas):
        separa nombres/apellidos y toma el texto de ubicación/EPS de las FK."""
        obj = super().save(commit=False)
        pn = (obj.nombres or '').split()
        obj.primer_nombre = (pn[0] if pn else '')[:60]
        obj.segundo_nombre = (' '.join(pn[1:]))[:60]
        pa = (obj.apellidos or '').split()
        obj.primer_apellido = (pa[0] if pa else '')[:60]
        obj.segundo_apellido = (' '.join(pa[1:]))[:60]
        if obj.municipio_nacimiento_id:
            try:
                obj.lugar_nacimiento = f"{obj.municipio_nacimiento.nombre}, {obj.municipio_nacimiento.departamento.nombre}"
            except Exception:
                pass
        if obj.municipio_residencia_id:
            obj.municipio_ciudad = obj.municipio_residencia.nombre
            try:
                obj.departamento = obj.municipio_residencia.departamento.nombre
            except Exception:
                pass
        if obj.eps_simat_id:
            obj.eps = obj.eps_simat.nombre
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class ImportarAspirantesForm(forms.Form):
    archivo_excel = forms.FileField(
        label=_("Selecciona un archivo Excel (.xlsx)"),
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
        label=_("Modo simulación (no crear registros, solo validar)"),
        help_text=_("Recomendado en la primera carga: valida el archivo y muestra errores fila por fila sin crear aspirantes."),
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
