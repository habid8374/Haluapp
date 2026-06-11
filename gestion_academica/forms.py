# gestion_academica/forms.py
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm 
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory


# Modelos propios de gestion_academica
from .models import (
    Grado, Estudiante, Docente, Familiar, Materia, PeriodoAcademico,
    Curso, DirectorCurso, EsquemaCalificacion, TipoActividad,
    ActividadCalificable, Calificacion, Deber, EntregaDeber,
    PlanCurricular, MencionReconocimiento, ArchivoPlanAcademico, Noticia,
    ConfiguracionInstitucion, Usuario, LeccionDiaria, ObservacionBoletin,
    DescriptorLogro, AnotacionObservador, DisponibilidadDocente, CitaReunion,
    Pregunta, Opcion, Eleccion, Aula, AreaAcademica, Logro, NivelEscolaridad,
    DimensionDesarrollo, EscalaCualitativa, LogroPreescolar, TicketSoporte,
    RespuestaTicket, PlaneacionClase, Candidato
)



# Modelos de finanzas que pueden necesitarse para querysets en formularios
from finanzas.models import InstitucionEducativa 

class UploadFileForm(forms.Form):
    file = forms.FileField(
        label="Seleccionar archivo Excel",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

class CustomUserCreationForm(UserCreationForm):
    """
    Un formulario genérico para CREAR cualquier tipo de usuario.
    Hereda de UserCreationForm para manejar la creación y confirmación de contraseña.
    """
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        # Añadimos los campos comunes que queremos en la creación.
        fields = ('username', 'first_name', 'last_name', 'email', 'institucion_asociada')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'institucion_asociada': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            # Reutilizamos tu excelente lógica de filtrado por institución
            self.fields['institucion_asociada'].queryset = filter_by_user_institution(self.fields['institucion_asociada'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion_asociada'].initial = request.user.institucion_asociada
                self.fields['institucion_asociada'].widget.attrs['disabled'] = True

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()


class CustomUserUpdateForm(forms.ModelForm):
    """
    Un formulario genérico para EDITAR cualquier tipo de usuario.
    """
    class Meta:
        model = get_user_model()
        fields = ['first_name', 'last_name', 'email', 'institucion_asociada', 'is_active', 'rol']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'institucion_asociada': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion_asociada'].queryset = filter_by_user_institution(self.fields['institucion_asociada'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion_asociada'].initial = request.user.institucion_asociada
                self.fields['institucion_asociada'].widget.attrs['disabled'] = True

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

# --- Formularios de Registro Inicial ---
class RegistroInicialForm(forms.ModelForm):
    username = forms.CharField(max_length=150, help_text="Nombre de usuario del administrador principal.")
    email = forms.EmailField(help_text="Correo electrónico del administrador principal.")
    password = forms.CharField(widget=forms.PasswordInput, help_text="Contraseña para el administrador principal.")
    password_confirm = forms.CharField(widget=forms.PasswordInput, label="Confirmar Contraseña")

    class Meta:
        model = InstitucionEducativa 
        fields = ['nombre', 'nit', 'direccion', 'telefono', 'correo_electronico', 'logo', 'eslogan'] 
        labels = {
            'nombre': 'Nombre de la Institución',
            'nit': 'NIT de la Institución',
            'direccion': 'Dirección de la Institución',
            'telefono': 'Teléfono de la Institución',
            'correo_electronico': 'Correo Electrónico de la Institución', 
            'logo': 'Logo de la Institución',
            'eslogan': 'Eslogan de la Institución (Opcional)',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'correo_electronico': forms.EmailInput(attrs={'class': 'form-control'}), 
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'eslogan': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean_nit(self):
        return (self.cleaned_data.get('nit') or '').strip()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Las contraseñas no coinciden.")

        nombre_institucion = cleaned_data.get('nombre')
        if not self.instance.pk and nombre_institucion and InstitucionEducativa.objects.filter(nombre=nombre_institucion).exists():
            raise forms.ValidationError({'nombre': "Ya existe una institución con este nombre."})

        return cleaned_data
    
    def save(self, commit=True):
        institucion = super().save(commit=False)
        if commit:
            institucion.save()
        return institucion

# --- Otros formularios de gestion_academica ---

def filter_by_user_institution(field_queryset, user):
    """
    Filtra un queryset basado en la institución del usuario.
    Maneja el caso especial donde el queryset es de InstitucionEducativa.
    """
    if user.is_superuser:
        return field_queryset.all()  # Superusuarios ven todo.

    if hasattr(user, 'institucion_asociada') and user.institucion_asociada:
        # Obtenemos el modelo del queryset que nos pasaron
        model = field_queryset.model

        # --- AQUÍ ESTÁ LA LÓGICA CLAVE ---
        # Si el queryset es del modelo InstitucionEducativa, filtramos por 'pk'.
        if model == InstitucionEducativa:
            return field_queryset.filter(pk=user.institucion_asociada.pk)
        
        # Para todos los demás modelos (Grado, Materia, etc.), filtramos por el campo 'institucion'.
        else:
            return field_queryset.filter(institucion=user.institucion_asociada)
        # ----------------------------------
    
    # Si el usuario no es superusuario y no tiene institución, no ve nada.
    return field_queryset.none()


class GradoForm(forms.ModelForm):
    class Meta:
        model = Grado
        # ✅ CORRECCIÓN: Nos aseguramos de que todos los nombres coincidan con el modelo
        fields = [
            'nombre', 
            'nivel_escolaridad', # <-- El nuevo campo para el nivel
            'orden', 
            'siguiente_grado', 
            'tipo_evaluacion',
            'institucion'
        ]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Esta lógica filtra los QuerySets para el admin, está correcta.
        if request and hasattr(request, 'user'):
            user = request.user
            if not user.is_superuser and hasattr(user, 'institucion_asociada'):
                institucion = user.institucion_asociada
                self.fields['siguiente_grado'].queryset = Grado.objects.filter(institucion=institucion)
                self.fields['nivel_escolaridad'].queryset = NivelEscolaridad.objects.filter(institucion=institucion)
                # Ocultamos el campo de institución para usuarios no-superadmin
                if 'institucion' in self.fields:
                    self.fields['institucion'].widget = forms.HiddenInput()
                    self.fields['institucion'].initial = institucion


class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        # Añadimos los nuevos campos a la lista de fields
        fields = [
            'documento_identidad', 'tipo_documento', 'codigo_estudiante',
            'fecha_nacimiento', 'lugar_nacimiento',
            'direccion', 'grado_actual', 'institucion', 'valor_matricula',
            'valor_mensualidad',
            'sexo', 'grupo_sanguineo', 'eps', 'discapacidad',
            'colegio_procedencia', 'municipio_ciudad', 'departamento',
            'descuentos',
        ]
        widgets = {
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'codigo_estudiante': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lugar_nacimiento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad y departamento'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'grado_actual': forms.Select(attrs={'class': 'form-select'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'valor_matricula': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_mensualidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sexo': forms.Select(attrs={'class': 'form-select'}),
            'grupo_sanguineo': forms.Select(attrs={'class': 'form-select'}),
            'eps': forms.TextInput(attrs={'class': 'form-control'}),
            'discapacidad': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dejar en blanco si no aplica'}),
            'colegio_procedencia': forms.TextInput(attrs={'class': 'form-control'}),
            'municipio_ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control'}),
            'descuentos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
        }
        labels = {
            'sexo': 'Sexo',
            'tipo_documento': 'Tipo de Documento',
            'lugar_nacimiento': 'Lugar de Nacimiento',
            'grupo_sanguineo': 'Grupo Sanguíneo',
            'eps': 'EPS / Entidad de Salud',
            'discapacidad': 'Discapacidad (si aplica)',
            'colegio_procedencia': 'Colegio de Procedencia',
            'municipio_ciudad': 'Municipio/Ciudad',
            'departamento': 'Departamento',
        }

    def __init__(self, *args, **kwargs):
        # Tu lógica de __init__ se mantiene intacta
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['grado_actual'].queryset = filter_by_user_institution(self.fields['grado_actual'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True

    def clean_documento_identidad(self):
        return (self.cleaned_data.get('documento_identidad') or '').strip()

    def clean_codigo_estudiante(self):
        return (self.cleaned_data.get('codigo_estudiante') or '').strip()


class DocenteForm(forms.ModelForm):
    class Meta:
        model = Docente
        fields = [
            'codigo_docente',
            'especialidad',
            'institucion',
            'modalidad_liquidacion',
            'valor_hora_docencia',
        ]
        widgets = {
            'codigo_docente': forms.TextInput(attrs={'class': 'form-control'}),
            'especialidad': forms.TextInput(attrs={'class': 'form-control'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'modalidad_liquidacion': forms.Select(attrs={'class': 'form-select'}),
            'valor_hora_docencia': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'codigo_docente': 'Código de Docente',
            'especialidad': 'Especialidad Principal',
            'institucion': 'Institución',
            'modalidad_liquidacion': 'Modalidad de liquidación',
            'valor_hora_docencia': 'Valor hora de referencia (opcional)',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = [
            'nombre_materia', 'codigo_materia', 'descripcion', 'institucion',
            'nombre_idioma_secundario', 'idioma_instruccion',
        ]
        widgets = {
            'nombre_materia':           forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_materia':           forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion':              forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'institucion':              forms.Select(attrs={'class': 'form-select'}),
            'nombre_idioma_secundario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mathematics, Natural Sciences…'}),
            'idioma_instruccion':       forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_materia':           'Nombre de la Materia',
            'codigo_materia':           'Código de Materia',
            'descripcion':              'Descripción',
            'institucion':              'Institución',
            'nombre_idioma_secundario': 'Nombre en Idioma Secundario',
            'idioma_instruccion':       'Idioma de Instrucción',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class PeriodoAcademicoForm(forms.ModelForm):
    class Meta:
        model = PeriodoAcademico
        fields = ['nombre', 'fecha_inicio', 'fecha_fin', 'año_escolar', 'activo', 'institucion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'año_escolar': forms.NumberInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre del Periodo',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_fin': 'Fecha de Fin',
            'año_escolar': 'Año Escolar',
            'activo': 'Activo',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['materia', 'grado', 'periodo_academico', 'docentes_asignados', 'institucion']
        widgets = {
            'materia': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
            'docentes_asignados': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'materia': 'Materia',
            'grado': 'Grado',
            'periodo_academico': 'Periodo Académico',
            'docentes_asignados': 'Docentes Asignados',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['materia'].queryset = filter_by_user_institution(self.fields['materia'].queryset, request.user)
            self.fields['grado'].queryset = filter_by_user_institution(self.fields['grado'].queryset, request.user)
            self.fields['periodo_academico'].queryset = filter_by_user_institution(self.fields['periodo_academico'].queryset, request.user)
            self.fields['docentes_asignados'].queryset = filter_by_user_institution(self.fields['docentes_asignados'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class DirectorCursoForm(forms.ModelForm):
    class Meta:
        model = DirectorCurso
        fields = ['docente', 'grado', 'periodo_academico', 'institucion']
        widgets = {
            'docente': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'docente': 'Docente Director',
            'grado': 'Grado Dirigido',
            'periodo_academico': 'Periodo Académico',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['docente'].queryset = filter_by_user_institution(self.fields['docente'].queryset, request.user)
            self.fields['grado'].queryset = filter_by_user_institution(self.fields['grado'].queryset, request.user)
            self.fields['periodo_academico'].queryset = filter_by_user_institution(self.fields['periodo_academico'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class EsquemaCalificacionForm(forms.ModelForm):
    class Meta:
        model = EsquemaCalificacion
        fields = ['nombre', 'descripcion', 'institucion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre del Esquema',
            'descripcion': 'Descripción',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class TipoActividadForm(forms.ModelForm):
    class Meta:
        model = TipoActividad
        # Añadimos todos los campos que el docente debe poder editar
        fields = ['nombre', 'descripcion', 'porcentaje']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
        }
        labels = {
            'nombre': 'Nombre de la Categoría (Ej: Exámenes, Tareas)',
            'descripcion': 'Descripción (Opcional)',
            'porcentaje': 'Porcentaje sobre la nota final (%)',
        }

    # El método __init__ no es necesario para este formulario, 
    # ya que no depende de filtros complejos. Lo mantenemos simple y robusto.
    def __init__(self, *args, **kwargs):
        kwargs.pop('request', None)
        super().__init__(*args, **kwargs)


class ActividadCalificableForm(forms.ModelForm):
    """
    Formulario para administradores para crear y editar actividades.
    Este es el formulario que estaba causando el error.
    """
    class Meta:
        model = ActividadCalificable
        
        # ✅ CORRECCIÓN CLAVE:
        # Eliminamos 'duracion_minutos' y 'numero_intentos_permitidos' de esta lista
        # porque ya no pertenecen a este modelo.
        fields = [
            'curso', 
            'tipo_actividad', 
            'titulo', 
            'descripcion', 
            'fecha_publicacion', 
            'fecha_entrega_limite', 
            'material_adjunto',
            'institucion' # <-- Añadido para que los superusuarios puedan asignarlo
        ]
        
        widgets = {
            'fecha_publicacion': forms.DateInput(attrs={'type': 'date'}),
            'fecha_entrega_limite': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Filtra los desplegables según la institución del usuario.
        """
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Si el usuario no es superadmin, ocultamos el campo de institución
        if request and not request.user.is_superuser:
            if 'institucion' in self.fields:
                self.fields['institucion'].widget = forms.HiddenInput()
        
        # Filtramos los QuerySets para que solo se muestren las opciones relevantes
        if request and hasattr(request.user, 'institucion_asociada'):
            institucion = request.user.institucion_asociada
            self.fields['curso'].queryset = Curso.objects.filter(institucion=institucion)
            self.fields['tipo_actividad'].queryset = TipoActividad.objects.filter(institucion=institucion)


class CalificacionForm(forms.ModelForm):
    class Meta:
        model = Calificacion
        fields = ['estudiante', 'actividad_calificable', 'valor_numerico', 'valor_cualitativo', 'observaciones', 'registrada_por', 'institucion']
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'actividad_calificable': forms.Select(attrs={'class': 'form-select'}),
            'valor_numerico': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'valor_cualitativo': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'registrada_por': forms.Select(attrs={'class': 'form-select'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'estudiante': 'Estudiante',
            'actividad_calificable': 'Actividad Calificable',
            'valor_numerico': 'Valor Numérico',
            'valor_cualitativo': 'Valor Cualitativo',
            'observaciones': 'Observaciones',
            'registrada_por': 'Registrada por',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['estudiante'].queryset = filter_by_user_institution(self.fields['estudiante'].queryset, request.user)
            self.fields['actividad_calificable'].queryset = filter_by_user_institution(self.fields['actividad_calificable'].queryset, request.user)
            self.fields['registrada_por'].queryset = filter_by_user_institution(self.fields['registrada_por'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class DeberForm(forms.ModelForm):
    class Meta:
        model = Deber
        fields = ['curso', 'titulo', 'descripcion', 'fecha_asignacion', 'fecha_entrega', 'material_adjunto', 'institucion']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_asignacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'material_adjunto': forms.FileInput(attrs={'class': 'form-control'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'curso': 'Curso',
            'titulo': 'Título del Deber',
            'descripcion': 'Descripción / Instrucciones',
            'fecha_asignacion': 'Fecha de Asignación',
            'fecha_entrega': 'Fecha Límite de Entrega',
            'material_adjunto': 'Material de Apoyo Adjunto',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario NO es superusuario, filtramos y deshabilitamos el campo institución
        if request and not request.user.is_superuser:
            institucion_usuario = request.user.institucion_asociada
            self.fields['institucion'].queryset = InstitucionEducativa.objects.filter(pk=institucion_usuario.pk)
            self.fields['institucion'].initial = institucion_usuario
            self.fields['institucion'].disabled = True
            self.fields['curso'].queryset = Curso.objects.filter(institucion=institucion_usuario).order_by('grado__orden')
        else:
            # Para el superusuario, el queryset de cursos empieza vacío.
            # Se poblará dinámicamente con JavaScript.
            self.fields['curso'].queryset = Curso.objects.none()
            # Si estamos editando, poblamos el queryset para que aparezca la opción guardada
            if self.instance and self.instance.pk and self.instance.institucion:
                self.fields['curso'].queryset = Curso.objects.filter(institucion=self.instance.institucion)


class EntregaDeberForm(forms.ModelForm):
    class Meta:
        model = EntregaDeber
        # ▼▼▼ CAMBIO CLAVE: Eliminamos 'institucion' de la lista ▼▼▼
        fields = ['archivo_adjunto_estudiante', 'comentarios_estudiante', 'calificacion_obtenida', 'comentarios_docente', 'fecha_calificacion']
        widgets = {
            'archivo_adjunto_estudiante': forms.FileInput(attrs={'class': 'form-control'}),
            'comentarios_estudiante': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'calificacion_obtenida': forms.TextInput(attrs={'class': 'form-control'}),
            'comentarios_docente': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_calificacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'archivo_adjunto_estudiante': 'Archivo Adjunto del Estudiante',
            'comentarios_estudiante': 'Comentarios del Estudiante',
            'calificacion_obtenida': 'Calificación Obtenida',
            'comentarios_docente': 'Comentarios del Docente',
            'fecha_calificacion': 'Fecha de Calificación',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if not request:
            return

        # Tu lógica para deshabilitar campos según el rol es perfecta y se mantiene.
        if hasattr(request.user, 'rol') and request.user.rol == 'estudiante':
            self.fields['calificacion_obtenida'].widget.attrs['readonly'] = True
            self.fields['comentarios_docente'].widget.attrs['readonly'] = True
            self.fields['fecha_calificacion'].widget.attrs['readonly'] = True
        elif hasattr(request.user, 'rol') and request.user.rol == 'docente':
            # Cuando el docente califica, no debe poder editar lo que subió el estudiante.
            self.fields['archivo_adjunto_estudiante'].widget = forms.HiddenInput() # Ocultamos el campo
            self.fields['comentarios_estudiante'].widget.attrs['readonly'] = True

class PlanCurricularForm(forms.ModelForm):
    class Meta:
        model = PlanCurricular
        fields = ['nombre', 'descripcion', 'documento_adjunto', 'grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'fecha_publicacion', 'institucion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'documento_adjunto': forms.FileInput(attrs={'class': 'form-control'}),
            'grado_asociado': forms.Select(attrs={'class': 'form-select'}),
            'materia_asociada': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico_asociado': forms.Select(attrs={'class': 'form-select'}),
            'fecha_publicacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre del Plan Curricular',
            'descripcion': 'Descripción Detallada',
            'documento_adjunto': 'Documento Adjunto',
            'grado_asociado': 'Grado Asociado',
            'materia_asociada': 'Materia Asociada',
            'periodo_academico_asociado': 'Periodo Académico Asociado',
            'fecha_publicacion': 'Fecha de Publicación/Vigencia',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['grado_asociado'].queryset = filter_by_user_institution(self.fields['grado_asociado'].queryset, request.user)
            self.fields['materia_asociada'].queryset = filter_by_user_institution(self.fields['materia_asociada'].queryset, request.user)
            self.fields['periodo_academico_asociado'].queryset = filter_by_user_institution(self.fields['periodo_academico_asociado'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True


class MencionReconocimientoForm(forms.ModelForm):
    class Meta:
        model = MencionReconocimiento
        # 1. Excluimos los campos que se llenarán automáticamente (quién lo otorga y la institución)
        fields = ['estudiante', 'curso', 'periodo', 'tipo', 'descripcion', 'fecha_otorgamiento']
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'periodo': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mérito Deportivo, Excelencia Académica'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_otorgamiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'estudiante': 'Estudiante Reconocido',
            'curso': 'Curso Relacionado (Opcional)',
            'periodo': 'Periodo Académico',
            'tipo': 'Tipo de Mención/Reconocimiento',
            'descripcion': 'Descripción Detallada',
            'fecha_otorgamiento': 'Fecha de Otorgamiento',
        }

    def __init__(self, *args, **kwargs):
        # Extraemos el 'request' que le pasamos desde la vista
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Si no hay un request, o el usuario no es un docente, no hacemos nada especial
        if not request or not hasattr(request.user, 'docente'):
            return

        docente = request.user.docente
        institucion = request.user.institucion_asociada
        periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=institucion).first()

        if periodo_activo:
            # 2. Lógica CLAVE: Filtramos los cursos para mostrar solo los del docente
            cursos_docente = Curso.objects.filter(docentes_asignados=docente, periodo_academico=periodo_activo)
            self.fields['curso'].queryset = cursos_docente
            
            # 3. Filtramos los estudiantes para mostrar solo los de los cursos del docente
            grados_docente_ids = cursos_docente.values_list('grado_id', flat=True).distinct()
            self.fields['estudiante'].queryset = Estudiante.objects.filter(grado_actual_id__in=grados_docente_ids, institucion=institucion)

            # 4. Filtramos y seleccionamos por defecto el periodo activo
            self.fields['periodo'].queryset = PeriodoAcademico.objects.filter(pk=periodo_activo.pk)
            self.fields['periodo'].initial = periodo_activo
        else:
            # Si no hay periodo activo, no mostramos opciones para evitar errores
            self.fields['curso'].queryset = Curso.objects.none()
            self.fields['estudiante'].queryset = Estudiante.objects.none()
            self.fields['periodo'].queryset = PeriodoAcademico.objects.none()
        
        # Hacemos que el campo curso sea opcional
        self.fields['curso'].required = False


class ArchivoPlanAcademicoForm(forms.ModelForm):
    class Meta:
        model = ArchivoPlanAcademico
        # Eliminamos 'institucion' de los campos porque la vista lo asignará automáticamente.
        fields = ['nombre_archivo_descriptivo', 'archivo', 'descripcion', 'tipo_documento', 'curso_asociado', 'materia_asociada']
        widgets = {
            'nombre_archivo_descriptivo': forms.TextInput(attrs={'class': 'form-control'}),
            'archivo': forms.FileInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tipo_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Guía, Taller, Presentación'}),
            'curso_asociado': forms.Select(attrs={'class': 'form-select'}),
            'materia_asociada': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_archivo_descriptivo': 'Nombre Descriptivo del Archivo',
            'archivo': 'Seleccionar Archivo',
            'descripcion': 'Descripción (Opcional)',
            'tipo_documento': 'Tipo de Documento',
            'curso_asociado': 'Asociar al Curso (Opcional)',
            'materia_asociada': 'Asociar a la Materia (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        # Extraemos el 'request' que le pasamos desde la vista
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Si no hay un request, no podemos hacer la lógica de filtrado
        if not request:
            return

        # --- LÓGICA MEJORADA ---
        
        # 1. Lógica específica para DOCENTES
        if hasattr(request.user, 'docente'):
            docente = request.user.docente
            institucion = request.user.institucion_asociada
            periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=institucion).first()

            # Filtramos el campo 'curso_asociado' para mostrar solo los cursos del docente
            if periodo_activo:
                self.fields['curso_asociado'].queryset = Curso.objects.filter(
                    docentes_asignados=docente,
                    periodo_academico=periodo_activo
                ).select_related('materia', 'grado').order_by('materia__nombre_materia')
            else:
                self.fields['curso_asociado'].queryset = Curso.objects.none()
            
            # Hacemos que el campo no sea obligatorio y tenga una etiqueta más clara
            self.fields['curso_asociado'].required = False
            self.fields['curso_asociado'].empty_label = "Sin asociar a un curso específico"
            
            # Filtramos las materias para que solo salgan las de su institución
            self.fields['materia_asociada'].queryset = Materia.objects.filter(institucion=institucion)
            self.fields['materia_asociada'].required = False
            self.fields['materia_asociada'].empty_label = "Sin asociar a una materia específica"

        # 2. Lógica para otros usuarios (ADMINISTRADORES)
        else:
            # Mantenemos la lógica original que ya tenías para los administradores
            self.fields['curso_asociado'].queryset = filter_by_user_institution(self.fields['curso_asociado'].queryset, request.user)
            self.fields['materia_asociada'].queryset = filter_by_user_institution(self.fields['materia_asociada'].queryset, request.user)

class NoticiaForm(forms.ModelForm):
    class Meta:
        model = Noticia
        fields = ['titulo', 'contenido', 'imagen_destacada', 'institucion']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'imagen_destacada': forms.FileInput(attrs={'class': 'form-control'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'titulo': 'Título de la Noticia/Anuncio',
            'contenido': 'Contenido',
            'imagen_destacada': 'Imagen Destacada',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True

class LeccionDiariaForm(forms.ModelForm):
    class Meta:
        model = LeccionDiaria
        fields = ['curso', 'fecha', 'tema_tratado', 'resumen_clase', 'archivo_adjunto']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tema_tratado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Introducción a las Fracciones'}),
            'resumen_clase': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'archivo_adjunto': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'tema_tratado': 'Tema Principal de la Clase',
            'resumen_clase': 'Resumen de la Lección y Actividades Realizadas',
            'archivo_adjunto': 'Material Adicional (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        # Extraemos el usuario (docente) que se pasa desde la vista
        docente_user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if docente_user and hasattr(docente_user, 'docente'):
            # Filtramos el campo 'curso' para que solo muestre los cursos
            # que imparte este docente en el periodo activo.
            periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=docente_user.institucion_asociada).first()
            if periodo_activo:
                self.fields['curso'].queryset = Curso.objects.filter(
                    docentes_asignados=docente_user.docente,
                    periodo_academico=periodo_activo
                ).select_related('materia', 'grado')
            else:
                self.fields['curso'].queryset = Curso.objects.none()                


class ObservacionBoletinForm(forms.ModelForm):
    class Meta:
        model = ObservacionBoletin
        fields = ['observacion']
        widgets = {
            'observacion': forms.Textarea(attrs={'rows': 4}),
        }

class DescriptorLogroForm(forms.ModelForm):
    class Meta:
        model = DescriptorLogro
        fields = ['materia', 'periodo_academico', 'grado', 'descripcion']
        widgets = {
            'materia': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'materia': 'Asignatura a la que pertenece el logro',
            'periodo_academico': 'Periodo académico de aplicación',
            'grado': 'Grado (opcional — deja en blanco para aplicar a todos)',
            'descripcion': 'Texto del logro o descriptor',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if request and hasattr(request.user, 'docente'):
            docente = request.user.docente
            institucion = request.user.institucion_asociada

            cursos_docente = Curso.objects.filter(docentes_asignados=docente, periodo_academico__activo=True)
            materias_ids = cursos_docente.values_list('materia_id', flat=True).distinct()
            self.fields['materia'].queryset = Materia.objects.filter(pk__in=materias_ids)
            self.fields['periodo_academico'].queryset = PeriodoAcademico.objects.filter(activo=True, institucion=institucion)
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)
        elif request:
            institucion = request.user.institucion_asociada
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)

class AnotacionObservadorForm(forms.ModelForm):
    class Meta:
        model = AnotacionObservador
        # Los campos que llenará el docente. El resto se asignará automáticamente.
        fields = ['tipo', 'descripcion', 'curso']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'tipo': 'Tipo de Anotación',
            'descripcion': 'Descripción Detallada del Hecho o Felicitación',
            'curso': 'Clase donde ocurrió (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Hacemos que el campo de curso no sea obligatorio
        self.fields['curso'].required = False
        self.fields['curso'].empty_label = "No asociar a un curso específico"

        if request and hasattr(request.user, 'docente'):
            # Filtramos el desplegable de cursos para mostrar solo los del docente
            docente = request.user.docente
            periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=docente.institucion).first()
            if periodo_activo:
                self.fields['curso'].queryset = Curso.objects.filter(
                    docentes_asignados=docente,
                    periodo_academico=periodo_activo
                )
            else:
                self.fields['curso'].queryset = Curso.objects.none()            

class DocenteActividadForm(forms.ModelForm):
    class Meta:
        model = ActividadCalificable
        # Este formulario incluye TODOS los campos que el docente puede editar
        fields = [
            'curso', 
            'tipo_actividad', 
            'titulo', 
            'descripcion', 
            'fecha_publicacion', 
            'fecha_entrega_limite', 
            'material_adjunto',
        ]
        
        # Widgets para mejorar la apariencia con Bootstrap y HTML5
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'tipo_actividad': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fecha_publicacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega_limite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'material_adjunto': forms.FileInput(attrs={'class': 'form-control'}),
        }
        
        # Etiquetas personalizadas para mayor claridad
        labels = {
            'curso': '¿A qué curso pertenece esta actividad?',
            'tipo_actividad': 'Categoría de la Actividad',
            'titulo': 'Nombre de la Actividad (Ej: Taller 1, Examen Parcial)',
            'descripcion': 'Instrucciones o descripción (Opcional)',
            'fecha_entrega_limite': 'Fecha de Realización o Entrega Límite (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        # Esta lógica para filtrar los desplegables es correcta y se mantiene
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request and hasattr(request.user, 'docente'):
            docente = request.user.docente
            institucion = request.user.institucion_asociada
            periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=institucion).first()
            if periodo_activo:
                self.fields['curso'].queryset = Curso.objects.filter(docentes_asignados=docente, periodo_academico=periodo_activo)
            else:
                self.fields['curso'].queryset = Curso.objects.none()
            self.fields['tipo_actividad'].queryset = TipoActividad.objects.filter(institucion=institucion)

class CalificarEntregaForm(forms.ModelForm):
    """
    Un formulario simple y dedicado exclusivamente para que el docente
    ingrese la nota y los comentarios de una tarea.
    """
    class Meta:
        model = EntregaDeber
        # Incluimos SOLAMENTE los campos que el docente debe llenar
        fields = ['calificacion_obtenida', 'comentarios_docente']
        widgets = {
            'calificacion_obtenida': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 4.5'}),
            'comentarios_docente': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Añade una retroalimentación para el estudiante...'}),
        }
        labels = {
            'calificacion_obtenida': 'Nota Asignada',
            'comentarios_docente': 'Comentarios o Retroalimentación',
        }      


class FamiliarForm(forms.ModelForm):
    """
    Formulario para los datos específicos del perfil de Familiar.
    """
    class Meta:
        model = Familiar
        # El campo 'usuario' se asignará desde la vista.
        fields = [
            'parentesco', 'telefono',
            'documento_identidad', 'tipo_documento',
            'ocupacion', 'lugar_trabajo', 'direccion',
            'estudiantes_asociados',
        ]
        widgets = {
            'parentesco': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Padre, Madre, Acudiente'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'ocupacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Docente, Comerciante…'}),
            'lugar_trabajo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Empresa u organización'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dirección de residencia'}),
            'estudiantes_asociados': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
        labels = {
            'documento_identidad': 'Número de Documento',
            'tipo_documento': 'Tipo de Documento',
            'ocupacion': 'Ocupación',
            'lugar_trabajo': 'Lugar de Trabajo / Empresa',
            'direccion': 'Dirección de Residencia',
        }

    def __init__(self, *args, **kwargs):
        # Filtramos el queryset para mostrar solo los estudiantes de la institución
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            user_inst = getattr(request.user, 'institucion_asociada', None)
            if user_inst:
                self.fields['estudiantes_asociados'].queryset = Estudiante.objects.filter(institucion=user_inst) 

class DisponibilidadDocenteForm(forms.ModelForm):
    """
    Formulario para que un docente defina un bloque de disponibilidad.
    """
    class Meta:
        model = DisponibilidadDocente
        fields = ['dia_semana', 'hora_inicio', 'hora_fin']
        widgets = {
            'dia_semana': forms.Select(attrs={'class': 'form-select'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
        labels = {
            'dia_semana': 'Día de la Semana',
            'hora_inicio': 'Disponible Desde',
            'hora_fin': 'Disponible Hasta',
        } 

class GestionCitaForm(forms.ModelForm):
    """
    Formulario para que el docente gestione una cita después de realizada.
    """
    class Meta:
        model = CitaReunion
        # Solo incluimos los campos que el docente debe poder editar
        fields = ['estado', 'observaciones_docente', 'acuerdos_compromisos']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observaciones_docente': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'acuerdos_compromisos': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }                              



class EleccionForm(forms.ModelForm):
    class Meta:
        model = Eleccion
        fields = ['nombre', 'descripcion', 'cargo', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }

class PreguntaForm(forms.ModelForm):
    class Meta:
        model = Pregunta
        # ✅ CORRECCIÓN: Añadimos los campos de configuración aquí.
        fields = [
            'enunciado', 
            'tipo', 
            'orden', 
            'duracion_minutos', 
            'numero_intentos_permitidos'
        ]
        
        widgets = {
            'enunciado': forms.Textarea(attrs={'rows': 4}),
            'duracion_minutos': forms.NumberInput(attrs={'placeholder': 'Ej: 5'}),
            'numero_intentos_permitidos': forms.NumberInput(attrs={'placeholder': 'Ej: 1'}),
        }
        labels = {
            'enunciado': 'Texto o enunciado de la pregunta',
            'tipo': 'Tipo de Pregunta',
            'orden': 'Orden de aparición',
            'duracion_minutos': 'Duración para esta pregunta (minutos)',
            'numero_intentos_permitidos': 'Intentos permitidos para esta pregunta',
        }
        help_texts = {
            'duracion_minutos': 'Dejar en blanco si no hay límite de tiempo.',
        }

# El OpcionFormSet se mantiene exactamente igual.
OpcionFormSet = forms.inlineformset_factory(
    Pregunta, Opcion,
    fields=('texto', 'es_correcta'),
    extra=4, can_delete=True,
    widgets={
        'texto': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Texto de la opción'}),
        'es_correcta': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    }
)

class ActividadConfigForm(forms.ModelForm):
    """
    Un formulario específico para editar la configuración clave
    de una actividad desde el panel de gestión de preguntas.
    """

    fecha_publicacion = forms.DateField(
        widget=forms.DateInput(
            attrs={'type': 'date'},
            format='%Y-%m-%d'
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        label="Fecha de Publicación"
    )

    fecha_entrega_limite = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date'},
            format='%Y-%m-%d'
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        label="Fecha Límite de Entrega (Opcional)"
    )
    
    class Meta:
        model = ActividadCalificable
        
        # ✅ Esta lista ahora coincide con los campos del modelo
        fields = [
            'fecha_publicacion', 
            'fecha_entrega_limite',
            'duracion_minutos', 
            'numero_intentos_permitidos'
        ]
        
        # Widgets para que los campos se vean bien
        widgets = {
            'fecha_publicacion': forms.DateInput(attrs={'type': 'date'}),
            'fecha_entrega_limite': forms.DateInput(attrs={'type': 'date'}),
            'duracion_minutos': forms.NumberInput(attrs={'placeholder': 'Ej: 30'}),
            'numero_intentos_permitidos': forms.NumberInput(attrs={'placeholder': 'Ej: 5', 'min': 1, 'max': 20}),
        }
        
        # Etiquetas personalizadas para mayor claridad
        labels = {
            'fecha_publicacion': 'Fecha de Publicación',
            'fecha_entrega_limite': 'Fecha Límite de Entrega (Opcional)',
            'duracion_minutos': 'Duración en Minutos (Opcional)',
            'numero_intentos_permitidos': 'Número de Intentos Permitidos',
        }
        
        # Textos de ayuda para guiar al docente
        help_texts = {
            'duracion_minutos': 'Dejar en blanco si no hay límite de tiempo.',
            'numero_intentos_permitidos': 'Por defecto se sugieren 5 intentos (etapa escolar); máximo 20.',
        }

class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        # Usamos los campos que definimos en el modelo mejorado
        fields = ['nombre', 'tipo', 'capacidad', 'ubicacion', 'recursos', 'institucion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'capacidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control'}),
            'recursos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre o Número del Aula',
            'tipo': 'Tipo de Aula',
            'capacidad': 'Capacidad de Estudiantes',
            'ubicacion': 'Ubicación (Ej: Edificio A, Piso 2)',
            'recursos': 'Recursos Disponibles (Ej: Proyector, Pizarra)',
            'institucion': 'Institución a la que pertenece',
        }

    def __init__(self, *args, **kwargs):
        # Reutilizamos tu excelente lógica de filtrado por institución
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            # Filtramos el campo 'institucion' para que el superusuario vea todas,
            # pero un admin normal solo vea la suya.
            self.fields['institucion'].queryset = filter_by_user_institution(
                self.fields['institucion'].queryset, request.user
            )
            # Si el usuario no es superadmin, pre-seleccionamos y bloqueamos su institución
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True

class AreaAcademicaForm(forms.ModelForm):
    materias = forms.ModelMultipleChoiceField(
        queryset=Materia.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'id': 'materias_disponibles', 'class': 'form-control', 'size': 10})
    )

    class Meta:
        model = AreaAcademica
        fields = ['nombre', 'institucion', 'materias']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if request and not request.user.is_superuser:
            self.fields['institucion'].initial = request.user.institucion_asociada
            self.fields['institucion'].widget.attrs['disabled'] = True
            self.fields['materias'].queryset = Materia.objects.filter(
                institucion=request.user.institucion_asociada
            )
        else:
            self.fields['materias'].queryset = Materia.objects.all()          

class LogroForm(forms.ModelForm):
    class Meta:
        model = Logro
        fields = ['materia', 'periodo', 'grado', 'descripcion', 'orden']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'grado': 'Grado (opcional — deja en blanco para aplicar a todos)',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'institucion_asociada'):
            institucion = user.institucion_asociada
            self.fields['materia'].queryset = Materia.objects.filter(institucion=institucion)
            self.fields['periodo'].queryset = PeriodoAcademico.objects.filter(institucion=institucion, activo=True)
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)


class DimensionDesarrolloForm(forms.ModelForm):
    """
    Formulario para crear y editar las Dimensiones de Desarrollo de Preescolar.
    """
    class Meta:
        model = DimensionDesarrollo
        fields = ['nombre', 'descripcion', 'orden']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cognitiva, Comunicativa'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'nombre': 'Nombre de la Dimensión',
            'descripcion': 'Descripción (Opcional)',
            'orden': 'Orden de Aparición',
        }
        help_texts = {
            'orden': 'Un número menor aparecerá primero en la lista y en los reportes.'
        }

class EscalaCualitativaForm(forms.ModelForm):
    class Meta:
        model = EscalaCualitativa
        fields = ['nombre_escala', 'abreviatura', 'descripcion', 'orden']
        widgets = {
            'nombre_escala': forms.TextInput(attrs={'class': 'form-control'}),
            'abreviatura': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
        }        

        
class LogroPreescolarForm(forms.ModelForm):
    """
    Formulario dedicado EXCLUSIVAMENTE para los Logros de Preescolar.
    """
    class Meta:
        model = LogroPreescolar
        fields = ['dimension', 'materia', 'periodo', 'grado', 'descripcion', 'orden']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'grado': 'Grado (opcional — deja en blanco para aplicar a todos)',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and hasattr(user, 'institucion_asociada'):
            institucion = user.institucion_asociada
            self.fields['dimension'].queryset = DimensionDesarrollo.objects.filter(institucion=institucion)
            self.fields['materia'].queryset = Materia.objects.filter(institucion=institucion)
            self.fields['periodo'].queryset = PeriodoAcademico.objects.filter(institucion=institucion, activo=True)
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)

class TicketSoporteForm(forms.ModelForm):
    class Meta:
        model = TicketSoporte
        fields = ['titulo', 'descripcion', 'prioridad']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 6}),
        }
        labels = {
            'titulo': 'Asunto o Título Corto',
            'descripcion': 'Por favor, describe el problema con el mayor detalle posible',
            'prioridad': 'Nivel de Prioridad',
        }   

class RespuestaTicketForm(forms.ModelForm):
    """
    Formulario para que el personal de soporte responda a un ticket.
    """
    class Meta:
        model = RespuestaTicket
        fields = ['mensaje', 'adjunto']
        widgets = {
            'mensaje': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Escribe tu respuesta aquí...'}),
        }
        labels = {
            'mensaje': 'Tu Respuesta',
            'adjunto': 'Adjuntar un archivo (Opcional)',
        }                 

class PlaneacionClaseForm(forms.ModelForm):
    """
    Formulario para que el docente defina los parámetros de la planeación
    que se enviarán a la IA.
    """
    # Sobrescribimos el campo 'curso' para filtrarlo por el docente actual
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.none(), # El queryset se llenará en la vista
        label="Curso y Materia",
        empty_label="--- Selecciona un curso ---"
    )

    class Meta:
        model = PlaneacionClase
        fields = ['titulo', 'curso', 'metodologia', 'duracion_clases']
        labels = {
            'titulo': '¿Cuál es el tema principal o nombre de la unidad?',
            'metodologia': '¿Qué metodología de enseñanza prefieres usar?',
            'duracion_clases': '¿En cuántas clases quieres desarrollar este tema?',
        }
        help_texts = {
            'titulo': 'Ej: "El Sistema Solar", "Introducción a las Fracciones", "El Renacimiento".',
            'duracion_clases': 'La IA generará un plan detallado para este número de clases.',
        }

    def __init__(self, *args, **kwargs):
        # Sacamos el 'user' que pasaremos desde la vista
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and hasattr(user, 'docente'):
            # Filtramos el queryset para mostrar solo los cursos asignados a este docente
            # en el periodo activo.
            periodo_activo = PeriodoAcademico.objects.filter(institucion=user.institucion_asociada, activo=True).first()
            if periodo_activo:
                self.fields['curso'].queryset = Curso.objects.filter(
                    docentes_asignados=user.docente,
                    periodo_academico=periodo_activo
                ).select_related('materia', 'grado')        

class LeccionDiariaIaForm(forms.ModelForm):
    """
    Formulario para editar una lección diaria existente.
    """
    class Meta:
        model = LeccionDiaria
        fields = ['fecha', 'tema_tratado', 'resumen_clase', 'archivo_adjunto']
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'resumen_clase': forms.Textarea(attrs={'rows': 8}),
        }
        labels = {
            'tema_tratado': 'Tema Tratado en la Clase',
            'resumen_clase': 'Resumen y Actividades Realizadas',
            'archivo_adjunto': 'Adjuntar un nuevo archivo (opcional)',
        }                

class CandidatoForm(forms.ModelForm):
    """
    Formulario para registrar un estudiante como candidato en una elección.
    """
    # Hacemos que el campo 'estudiante' sea un selector con buscador para facilidad de uso.
    estudiante = forms.ModelChoiceField(
        queryset=Estudiante.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}), # Puedes añadir 'select2' si usas esa librería
        label="Estudiante Candidato"
    )

    class Meta:
        model = Candidato
        fields = ['estudiante', 'foto', 'propuesta']
        widgets = {
            'propuesta': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        # Sacamos la 'institucion' que pasaremos desde la vista para filtrar
        institucion = kwargs.pop('institucion', None)
        super().__init__(*args, **kwargs)
        
        if institucion:
            # Filtramos el queryset para mostrar solo los estudiantes activos de la institución correcta
            self.fields['estudiante'].queryset = Estudiante.objects.filter(
                institucion=institucion, 
                activo=True
            ).select_related('usuario')        

class UserEditForm(forms.ModelForm):
    """
    Formulario para que un administrador edite los datos de un usuario.
    """
    class Meta:
        model = Usuario
        fields = ['first_name', 'last_name', 'email', 'rol', 'is_active']
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
            'rol': 'Rol en la Plataforma',
            'is_active': '¿Cuenta Activa?',
        }
        help_texts = {
            'is_active': 'Desmarca esta casilla para desactivar la cuenta del usuario sin eliminarla.'
        }

class UserPasswordChangeForm(forms.Form):
    """
    Formulario dedicado para cambiar la contraseña de un usuario.
    """
    new_password1 = forms.CharField(
        label="Nueva Contraseña",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label="Confirmar Nueva Contraseña",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )

    def clean_new_password2(self):
        password_1 = self.cleaned_data.get("new_password1")
        password_2 = self.cleaned_data.get("new_password2")
        if password_1 and password_2 and password_1 != password_2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password_2            