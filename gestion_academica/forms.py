# gestion_academica/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset


# Modelos propios de gestion_academica
from .models import (
    Grado, Estudiante, Docente, Familiar, Materia, PeriodoAcademico,
    Curso, DirectorCurso, TipoActividad,
    ActividadCalificable, Calificacion, Deber, EntregaDeber,
    PlanCurricular, MencionReconocimiento, ArchivoPlanAcademico, Noticia,
    ConfiguracionInstitucion, Usuario, LeccionDiaria, ObservacionBoletin,
    DescriptorLogro, AnotacionObservador, DisponibilidadDocente, CitaReunion,
    DisponibilidadOrientador, CitaOrientacion, SeguimientoOrientacion,
    Pregunta, Opcion, Eleccion, Aula, AreaAcademica, NivelEscolaridad,
    DimensionDesarrollo, EscalaCualitativa, LogroPreescolar, TicketSoporte,
    RespuestaTicket, PlaneacionClase, Candidato, CaracterizacionEstudiante,
    JustificacionInasistencia, PerfilAccesibilidad,
)



# Modelos de finanzas que pueden necesitarse para querysets en formularios
from finanzas.models import InstitucionEducativa


class PerfilAccesibilidadForm(forms.ModelForm):
    """Editor del perfil de accesibilidad del estudiante (Ola 2)."""

    class Meta:
        model = PerfilAccesibilidad
        fields = [
            'activo', 'font', 'contrast', 'dyslexia', 'spacing',
            'reduce_motion', 'easy_read', 'tts_default',
            'tiempo_extra_pct', 'enunciado_simplificado', 'notas',
        ]
        widgets = {
            'font': forms.Select(attrs={'class': 'form-select'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'contrast': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dyslexia': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'spacing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reduce_motion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'easy_read': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tts_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enunciado_simplificado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tiempo_extra_pct': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'step': 5}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_tiempo_extra_pct(self):
        v = self.cleaned_data.get('tiempo_extra_pct') or 0
        return min(int(v), 100)

class UploadFileForm(forms.Form):
    file = forms.FileField(
        label=_("Seleccionar archivo Excel"),
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
        # Cuando el nombre se captura como 4 campos SIMAT en otro formulario
        # (p. ej. estudiante), se ocultan aquí para no duplicar la captura.
        ocultar_nombre = kwargs.pop('ocultar_nombre', False)
        super().__init__(*args, **kwargs)
        if ocultar_nombre:
            self.fields.pop('first_name', None)
            self.fields.pop('last_name', None)
        if request:
            self.fields['institucion_asociada'].queryset = filter_by_user_institution(self.fields['institucion_asociada'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion_asociada'].initial = request.user.institucion_asociada
                self.fields['institucion_asociada'].widget.attrs['disabled'] = True

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

# --- Formularios de Registro Inicial ---
class RegistroInicialForm(forms.ModelForm):
    username = forms.CharField(max_length=150, help_text=_("Nombre de usuario del administrador principal."))
    email = forms.EmailField(help_text=_("Correo electrónico del administrador principal."))
    password = forms.CharField(widget=forms.PasswordInput, help_text=_("Contraseña para el administrador principal."))
    password_confirm = forms.CharField(widget=forms.PasswordInput, label=_("Confirmar Contraseña"))

    class Meta:
        model = InstitucionEducativa 
        fields = ['nombre', 'nit', 'direccion', 'telefono', 'correo_electronico', 'logo', 'eslogan'] 
        labels = {
            'nombre': _('Nombre de la Institución'),
            'nit': _('NIT de la Institución'),
            'direccion': _('Dirección de la Institución'),
            'telefono': _('Teléfono de la Institución'),
            'correo_electronico': _('Correo Electrónico de la Institución'), 
            'logo': _('Logo de la Institución'),
            'eslogan': _('Eslogan de la Institución (Opcional)'),
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
            'simat_grado_id',  # ID oficial del grado en el SIMAT (reporte MEN)
            'institucion'
        ]
        widgets = {
            'simat_grado_id': forms.Select(attrs={'class': 'form-select'}),
        }

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
        # CRITERIO ÚNICO (igual que el aspirante): sin duplicados. La ubicación
        # (nacimiento/residencia) y la EPS se capturan por CÓDIGO en la
        # Caracterización SIMAT; los textos internos (lugar_nacimiento,
        # municipio_ciudad, departamento, eps) se DERIVAN de esa selección.
        fields = [
            'documento_identidad', 'tipo_documento', 'codigo_estudiante',
            'fecha_nacimiento',
            'direccion', 'grado_actual', 'grupo', 'institucion', 'valor_matricula',
            'valor_mensualidad',
            'sexo', 'grupo_sanguineo', 'discapacidad',
            'colegio_procedencia',
            'descuentos',
        ]
        widgets = {
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-select'}),
            'codigo_estudiante': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'lugar_nacimiento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ciudad y departamento'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'grado_actual': forms.Select(attrs={'class': 'form-select'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
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
            'sexo': _('Sexo'),
            'tipo_documento': _('Tipo de Documento'),
            'lugar_nacimiento': _('Lugar de Nacimiento'),
            'grupo_sanguineo': _('Grupo Sanguíneo'),
            'eps': _('EPS / Entidad de Salud'),
            'discapacidad': _('Discapacidad (si aplica)'),
            'colegio_procedencia': _('Colegio de Procedencia'),
            'municipio_ciudad': _('Municipio/Ciudad'),
            'departamento': _('Departamento'),
        }

    def __init__(self, *args, **kwargs):
        # Tu lógica de __init__ se mantiene intacta
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # La fecha nativa (type=date) intercambia siempre en formato ISO.
        self.fields['fecha_nacimiento'].input_formats = ['%Y-%m-%d', '%d/%m/%Y']

        if request:
            self.fields['grado_actual'].queryset = filter_by_user_institution(self.fields['grado_actual'].queryset, request.user)
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if 'grupo' in self.fields:
                self.fields['grupo'].queryset = filter_by_user_institution(
                    self.fields['grupo'].queryset, request.user
                ).filter(activo=True).select_related('grado')

        # El grupo es opcional y se filtra a la institución del estudiante.
        if 'grupo' in self.fields:
            self.fields['grupo'].required = False
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].disabled = True

        # Colegios que NO usan el módulo financiero (p. ej. oficiales/gratuitos)
        # no cobran matrícula ni pensión: esos campos quedan OPCIONALES (default 0),
        # sin asterisco de obligatorio.
        institucion = None
        if getattr(self.instance, 'institucion_id', None):
            institucion = self.instance.institucion
        elif request is not None:
            institucion = getattr(request.user, 'institucion_asociada', None)
        if institucion is not None and not getattr(institucion, 'usa_modulo_financiero', True):
            for campo in ('valor_matricula', 'valor_mensualidad'):
                if campo in self.fields:
                    self.fields[campo].required = False
                    self.fields[campo].initial = 0
                    self.fields[campo].help_text = _("Tu institución no cobra este concepto; puede quedar en 0.")

    def clean_documento_identidad(self):
        return (self.cleaned_data.get('documento_identidad') or '').strip()

    def clean_codigo_estudiante(self):
        return (self.cleaned_data.get('codigo_estudiante') or '').strip()

    def clean_valor_matricula(self):
        from decimal import Decimal
        return self.cleaned_data.get('valor_matricula') or Decimal('0.00')

    def clean_valor_mensualidad(self):
        from decimal import Decimal
        return self.cleaned_data.get('valor_mensualidad') or Decimal('0.00')


class CaracterizacionEstudianteForm(forms.ModelForm):
    """Caracterización SIMAT/SIMPADE del estudiante (a la par del Aspirante).
    Todos los campos opcionales; las FK van por desplegable de catálogo."""

    class Meta:
        model = CaracterizacionEstudiante
        fields = [
            # ── Nombres SIMAT: fuente única del nombre (el login/nombre mostrado
            #    se compone de estos 4 campos; por eso NO se piden en "Datos de
            #    Usuario"). ──
            'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido',
            'pais_origen', 'zona_residencia',
            'regimen_salud', 'discapacidad_categoria', 'capacidad_excepcional',
            'grupo_etnico', 'estrato', 'sisben_grupo', 'sisben_puntaje',
            'victima_conflicto', 'tipo_poblacion_victima',
            'srpa', 'apoyo_academico_especial',
            # ── SIMAT (espejo del Aspirante) ──
            'nacionalidad', 'lugar_expedicion_departamento', 'lugar_expedicion_municipio',
            'pais_nacimiento', 'departamento_nacimiento', 'municipio_nacimiento',
            'departamento_residencia', 'municipio_residencia', 'barrio', 'campesino',
            'etnia_simat', 'resguardo', 'eps_simat',
            # sede / jornada / grupo NO se capturan aquí: se definen al elegir el
            # Grupo del estudiante (arriba, en "Datos del estudiante"), del cual
            # la sede y la jornada se derivan. Así no se duplica la selección.
            'modelo_educativo', 'fuente_recursos',
            'internado', 'matricula_contratada', 'repitente', 'situacion_academica_anterior',
            # ── SIMAT/SIMPADE codificados (reporte plano oficial) ──
            'sisben_simat', 'caracter', 'especialidad', 'metodologia',
            'situacion_va', 'condicion_va', 'fuente_recurso', 'tipo_internado',
            'valoracion_p1', 'valoracion_p2', 'subsidiado', 'es_nuevo',
            'proviene_sector_privado', 'proviene_otro_municipio',
            'madre_cabeza_familia', 'hijo_madre_cabeza_familia',
            'beneficiario_veterano', 'beneficiario_heroe',
            'numero_convenio', 'institucion_bienestar',
            'expulsor_departamento', 'expulsor_municipio',
        ]
        widgets = {
            'primer_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'segundo_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'primer_apellido': forms.TextInput(attrs={'class': 'form-control'}),
            'segundo_apellido': forms.TextInput(attrs={'class': 'form-control'}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ['lugar_expedicion_departamento', 'lugar_expedicion_municipio',
                  'departamento_nacimiento', 'municipio_nacimiento',
                  'departamento_residencia', 'municipio_residencia',
                  'etnia_simat', 'resguardo', 'eps_simat']:
            if f in self.fields:
                self.fields[f].required = False

        # Nombres SIMAT: primer nombre y primer apellido obligatorios.
        self.fields['primer_nombre'].required = True
        self.fields['primer_apellido'].required = True
        self.fields['segundo_nombre'].required = False
        self.fields['segundo_apellido'].required = False
        # Estudiante existente sin los 4 campos: prellenar desde el nombre del
        # usuario (para que no se vean vacíos la primera vez).
        inst = getattr(self, 'instance', None)
        usuario = getattr(getattr(inst, 'estudiante', None), 'usuario', None)
        if usuario is not None:
            if not (inst.primer_nombre or '') and (usuario.first_name or ''):
                pn = usuario.first_name.split()
                self.fields['primer_nombre'].initial = pn[0] if pn else ''
                self.fields['segundo_nombre'].initial = ' '.join(pn[1:])
            if not (inst.primer_apellido or '') and (usuario.last_name or ''):
                pa = usuario.last_name.split()
                self.fields['primer_apellido'].initial = pa[0] if pa else ''
                self.fields['segundo_apellido'].initial = ' '.join(pa[1:])

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True
        self.helper.layout = Layout(
            Fieldset(_("Nombre completo (SIMAT)"),
                'primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'),
            Fieldset(_("Identificación (SIMAT)"),
                'nacionalidad', 'lugar_expedicion_departamento', 'lugar_expedicion_municipio'),
            Fieldset(_("Nacimiento y residencia (DANE)"),
                'pais_origen', 'pais_nacimiento', 'departamento_nacimiento', 'municipio_nacimiento',
                'departamento_residencia', 'municipio_residencia', 'barrio', 'zona_residencia'),
            Fieldset(_("Salud y grupos"),
                'regimen_salud', 'eps_simat', 'discapacidad_categoria', 'capacidad_excepcional',
                'grupo_etnico', 'etnia_simat', 'resguardo'),
            Fieldset(_("Socio-económico (SIMPADE)"),
                'estrato', 'sisben_grupo', 'sisben_simat', 'sisben_puntaje', 'victima_conflicto',
                'tipo_poblacion_victima', 'srpa', 'campesino', 'apoyo_academico_especial',
                'expulsor_departamento', 'expulsor_municipio',
                'proviene_sector_privado', 'proviene_otro_municipio',
                'madre_cabeza_familia', 'hijo_madre_cabeza_familia',
                'beneficiario_veterano', 'beneficiario_heroe'),
            Fieldset(_("Matrícula (SIMAT oficial)"),
                'modelo_educativo', 'fuente_recursos',
                'internado', 'matricula_contratada', 'repitente', 'situacion_academica_anterior',
                'caracter', 'especialidad', 'metodologia',
                'situacion_va', 'condicion_va', 'fuente_recurso', 'tipo_internado',
                'valoracion_p1', 'valoracion_p2', 'subsidiado', 'es_nuevo',
                'numero_convenio', 'institucion_bienestar'),
        )


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
            'codigo_docente': _('Código de Docente'),
            'especialidad': _('Especialidad Principal'),
            'institucion': _('Institución'),
            'modalidad_liquidacion': _('Modalidad de liquidación'),
            'valor_hora_docencia': _('Valor hora de referencia (opcional)'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].disabled = True


class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = [
            'nombre_materia', 'nivel_escolaridad', 'codigo_materia', 'descripcion', 'institucion',
            'nombre_idioma_secundario', 'idioma_instruccion',
        ]
        widgets = {
            'nombre_materia':           forms.TextInput(attrs={'class': 'form-control'}),
            'nivel_escolaridad':        forms.Select(attrs={'class': 'form-select'}),
            'codigo_materia':           forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion':              forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'institucion':              forms.Select(attrs={'class': 'form-select'}),
            'nombre_idioma_secundario': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mathematics, Natural Sciences…'}),
            'idioma_instruccion':       forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_materia':           _('Nombre de la Materia'),
            'nivel_escolaridad':        _('Nivel de Escolaridad'),
            'codigo_materia':           _('Código de Materia'),
            'descripcion':              _('Descripción'),
            'institucion':              _('Institución'),
            'nombre_idioma_secundario': _('Nombre en Idioma Secundario'),
            'idioma_instruccion':       _('Idioma de Instrucción'),
        }
        help_texts = {
            'nivel_escolaridad': _('Preescolar, Primaria, Secundaria o Media. Permite tener, p. ej., "Matemáticas" de Primaria y otra de Secundaria.'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # El nivel es obligatorio al crear/editar materias nuevas (el modelo lo
        # deja nullable solo por compatibilidad con datos previos).
        self.fields['nivel_escolaridad'].required = True

        # Institución de contexto para acotar el desplegable de nivel: la de la
        # materia que se edita (aplica incluso al superusuario, para no mezclar
        # niveles de otros colegios) o, al crear, la del usuario.
        inst_ctx = None
        if getattr(self.instance, 'institucion_id', None):
            inst_ctx = self.instance.institucion
        elif request and not request.user.is_superuser:
            inst_ctx = getattr(request.user, 'institucion_asociada', None)
        if inst_ctx is not None:
            self.fields['nivel_escolaridad'].queryset = NivelEscolaridad.objects.filter(institucion=inst_ctx)

        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            institucion = getattr(request.user, 'institucion_asociada', None)
            if not request.user.is_superuser and institucion:
                self.fields['institucion'].initial = institucion
                self.fields['institucion'].disabled = True

    def clean(self):
        cleaned = super().clean()
        nivel = cleaned.get('nivel_escolaridad')
        inst = cleaned.get('institucion') or getattr(self.instance, 'institucion', None)
        # Defensa multi-institución: el nivel debe ser de la misma institución
        # de la materia (bloquea manipulación del POST con un nivel de otro colegio).
        if nivel and inst and nivel.institucion_id != inst.pk:
            self.add_error('nivel_escolaridad', _("El nivel de escolaridad debe pertenecer a la misma institución de la materia."))
        return cleaned


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
            'nombre': _('Nombre del Periodo'),
            'fecha_inicio': _('Fecha de Inicio'),
            'fecha_fin': _('Fecha de Fin'),
            'año_escolar': _('Año Escolar'),
            'activo': _('Activo'),
            'institucion': _('Institución'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].disabled = True


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
            'materia': _('Materia'),
            'grado': _('Grado'),
            'periodo_academico': _('Periodo Académico'),
            'docentes_asignados': _('Docentes Asignados'),
            'institucion': _('Institución'),
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
                self.fields['institucion'].disabled = True

    def clean(self):
        cleaned = super().clean()
        materia = cleaned.get('materia')
        grado = cleaned.get('grado')
        # La materia debe pertenecer al mismo nivel de escolaridad del grado.
        # Solo se valida cuando ambos tienen nivel definido (datos previos sin
        # nivel no se bloquean).
        if materia and grado and materia.nivel_escolaridad_id and grado.nivel_escolaridad_id:
            if materia.nivel_escolaridad_id != grado.nivel_escolaridad_id:
                self.add_error('materia', _(
                    "La materia «%(m)s» es del nivel %(mn)s, pero el grado «%(g)s» es de %(gn)s. "
                    "Elige una materia del mismo nivel."
                ) % {
                    'm': materia.nombre_materia,
                    'mn': materia.nivel_escolaridad.nombre,
                    'g': grado.nombre,
                    'gn': grado.nivel_escolaridad.nombre,
                })
        return cleaned


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
            'docente': _('Docente Director'),
            'grado': _('Grado Dirigido'),
            'periodo_academico': _('Periodo Académico'),
            'institucion': _('Institución'),
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
                self.fields['institucion'].disabled = True


class TipoActividadForm(forms.ModelForm):
    class Meta:
        model = TipoActividad
        fields = ['nombre', 'descripcion', 'porcentaje']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
        }
        labels = {
            'nombre': _('Nombre de la Categoría (Ej: Exámenes, Tareas)'),
            'descripcion': _('Descripción (Opcional)'),
            'porcentaje': _('Porcentaje sobre la nota final (%)'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request and request.user.is_superuser:
            self.fields['institucion'] = forms.ModelChoiceField(
                queryset=InstitucionEducativa.objects.all().order_by('nombre'),
                label=_('Institución'),
                widget=forms.Select(attrs={'class': 'form-select'}),
                required=True,
            )


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
            'estudiante': _('Estudiante'),
            'actividad_calificable': _('Actividad Calificable'),
            'valor_numerico': _('Valor Numérico'),
            'valor_cualitativo': _('Valor Cualitativo'),
            'observaciones': _('Observaciones'),
            'registrada_por': _('Registrada por'),
            'institucion': _('Institución'),
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
                self.fields['institucion'].disabled = True


class DeberForm(forms.ModelForm):
    class Meta:
        model = Deber
        fields = ['curso', 'titulo', 'descripcion', 'tipo_actividad', 'fecha_asignacion', 'fecha_entrega', 'material_adjunto', 'audio', 'institucion']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tipo_actividad': forms.Select(attrs={'class': 'form-select'}),
            'fecha_asignacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'material_adjunto': forms.FileInput(attrs={'class': 'form-control'}),
            'audio': forms.FileInput(attrs={'class': 'form-control', 'accept': 'audio/*'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'curso': _('Curso'),
            'titulo': _('Título del Deber'),
            'descripcion': _('Descripción / Instrucciones'),
            'tipo_actividad': _('Categoría de la actividad (Saber Ser, Saber Hacer, …)'),
            'fecha_asignacion': _('Fecha de Asignación'),
            'fecha_entrega': _('Fecha Límite de Entrega'),
            'material_adjunto': _('Material de Apoyo Adjunto'),
            'audio': _('Audio de apoyo (opcional)'),
            'institucion': _('Institución'),
        }
        help_texts = {
            'tipo_actividad': _('Determina con qué porcentaje pondera esta nota en el boletín. Es obligatoria para que la nota cuente.'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # La categoría es obligatoria: sin ella la nota no pondera en el boletín.
        self.fields['tipo_actividad'].required = True
        self.fields['tipo_actividad'].empty_label = 'Selecciona una categoría…'

        # Si el usuario NO es superusuario, filtramos y deshabilitamos el campo institución
        if request and not request.user.is_superuser:
            institucion_usuario = request.user.institucion_asociada
            self.fields['institucion'].queryset = InstitucionEducativa.objects.filter(pk=institucion_usuario.pk)
            self.fields['institucion'].initial = institucion_usuario
            self.fields['institucion'].disabled = True
            self.fields['curso'].queryset = Curso.objects.filter(institucion=institucion_usuario).order_by('grado__orden')
            self.fields['tipo_actividad'].queryset = TipoActividad.objects.filter(institucion=institucion_usuario).order_by('nombre')
        else:
            # Para el superusuario, el queryset de cursos empieza vacío.
            # Se poblará dinámicamente con JavaScript.
            self.fields['curso'].queryset = Curso.objects.none()
            # Si estamos editando, poblamos el queryset para que aparezca la opción guardada
            if self.instance and self.instance.pk and self.instance.institucion:
                self.fields['curso'].queryset = Curso.objects.filter(institucion=self.instance.institucion)
                self.fields['tipo_actividad'].queryset = TipoActividad.objects.filter(institucion=self.instance.institucion).order_by('nombre')

    def clean_audio(self):
        audio = self.cleaned_data.get('audio')
        # Solo validamos cuando se sube un archivo nuevo (no un FieldFile ya guardado).
        if audio and hasattr(audio, 'content_type'):
            if audio.size > 20 * 1024 * 1024:
                raise forms.ValidationError(_("El audio supera el tamaño máximo (20 MB)."))
            nombre = (getattr(audio, 'name', '') or '').lower()
            ext = nombre.rsplit('.', 1)[-1] if '.' in nombre else ''
            if ext not in ('mp3', 'wav', 'ogg', 'oga', 'm4a', 'aac', 'webm', 'opus'):
                raise forms.ValidationError(_("Formato de audio no permitido. Usa MP3, WAV, OGG, M4A, AAC o WEBM."))
        return audio


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
            'archivo_adjunto_estudiante': _('Archivo Adjunto del Estudiante'),
            'comentarios_estudiante': _('Comentarios del Estudiante'),
            'calificacion_obtenida': _('Calificación Obtenida'),
            'comentarios_docente': _('Comentarios del Docente'),
            'fecha_calificacion': _('Fecha de Calificación'),
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
            'nombre': _('Nombre del Plan Curricular'),
            'descripcion': _('Descripción Detallada'),
            'documento_adjunto': _('Documento Adjunto'),
            'grado_asociado': _('Grado Asociado'),
            'materia_asociada': _('Materia Asociada'),
            'periodo_academico_asociado': _('Periodo Académico Asociado'),
            'fecha_publicacion': _('Fecha de Publicación/Vigencia'),
            'institucion': _('Institución'),
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
                self.fields['institucion'].disabled = True


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
            'estudiante': _('Estudiante Reconocido'),
            'curso': _('Curso Relacionado (Opcional)'),
            'periodo': _('Periodo Académico'),
            'tipo': _('Tipo de Mención/Reconocimiento'),
            'descripcion': _('Descripción Detallada'),
            'fecha_otorgamiento': _('Fecha de Otorgamiento'),
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
            'nombre_archivo_descriptivo': _('Nombre Descriptivo del Archivo'),
            'archivo': _('Seleccionar Archivo'),
            'descripcion': _('Descripción (Opcional)'),
            'tipo_documento': _('Tipo de Documento'),
            'curso_asociado': _('Asociar al Curso (Opcional)'),
            'materia_asociada': _('Asociar a la Materia (Opcional)'),
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
            'titulo': _('Título de la Noticia/Anuncio'),
            'contenido': _('Contenido'),
            'imagen_destacada': _('Imagen Destacada'),
            'institucion': _('Institución'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        if request:
            self.fields['institucion'].queryset = filter_by_user_institution(self.fields['institucion'].queryset, request.user)
            if not request.user.is_superuser and request.user.institucion_asociada:
                self.fields['institucion'].initial = request.user.institucion_asociada
                self.fields['institucion'].disabled = True

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
            'tema_tratado': _('Tema Principal de la Clase'),
            'resumen_clase': _('Resumen de la Lección y Actividades Realizadas'),
            'archivo_adjunto': _('Material Adicional (Opcional)'),
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
        fields = ['materia', 'periodo_academico', 'grado', 'dimension', 'descripcion']
        widgets = {
            'materia': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'dimension': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'materia': _('Asignatura a la que pertenece el logro'),
            'periodo_academico': _('Periodo académico de aplicación'),
            'grado': _('Grado (opcional — deja en blanco para aplicar a todos)'),
            'dimension': _('Dimensión (opcional — solo preescolar)'),
            'descripcion': _('Texto del logro o descriptor'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # La dimensión es opcional (solo preescolar); no obligar en el formulario.
        if 'dimension' in self.fields:
            self.fields['dimension'].required = False

        if request and hasattr(request.user, 'docente'):
            # Docente: solo sus materias asignadas
            docente = request.user.docente
            institucion = request.user.institucion_asociada
            cursos_docente = Curso.objects.filter(docentes_asignados=docente, periodo_academico__activo=True)
            materias_ids = cursos_docente.values_list('materia_id', flat=True).distinct()
            self.fields['materia'].queryset = Materia.objects.filter(pk__in=materias_ids)
            self.fields['periodo_academico'].queryset = PeriodoAcademico.objects.filter(activo=True, institucion=institucion)
            self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)
            self.fields['dimension'].queryset = DimensionDesarrollo.objects.filter(institucion=institucion)
        elif request:
            # Coordinador u otro rol: todas las materias/periodos/grados de la institución
            institucion = getattr(request.user, 'institucion_asociada', None)
            if institucion:
                self.fields['materia'].queryset = Materia.objects.filter(institucion=institucion)
                self.fields['periodo_academico'].queryset = PeriodoAcademico.objects.filter(institucion=institucion)
                self.fields['grado'].queryset = Grado.objects.filter(institucion=institucion)
                self.fields['dimension'].queryset = DimensionDesarrollo.objects.filter(institucion=institucion)

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
            'tipo': _('Tipo de Anotación'),
            'descripcion': _('Descripción Detallada del Hecho o Felicitación'),
            'curso': _('Clase donde ocurrió (Opcional)'),
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
        elif request and not request.user.is_superuser:
            # Coordinador / rector / orientador: cursos de SU institución (no de
            # otras). Cierra la fuga multi-institución del desplegable.
            inst = getattr(request.user, 'institucion_asociada', None)
            if inst:
                periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=inst).first()
                qs = Curso.objects.filter(institucion=inst)
                if periodo_activo:
                    qs = qs.filter(periodo_academico=periodo_activo)
                self.fields['curso'].queryset = qs
            else:
                self.fields['curso'].queryset = Curso.objects.none()

        # Al EDITAR: garantizar que el curso ya asociado siga siendo
        # seleccionable aunque sea de un período anterior (no aparecería en el
        # queryset filtrado por período activo).
        inst_actual = getattr(self, 'instance', None)
        if inst_actual and inst_actual.pk and inst_actual.curso_id:
            self.fields['curso'].queryset = (
                self.fields['curso'].queryset | Curso.objects.filter(pk=inst_actual.curso_id)
            ).distinct()

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
            'curso': _('¿A qué curso pertenece esta actividad?'),
            'tipo_actividad': _('Categoría de la Actividad'),
            'titulo': _('Nombre de la Actividad (Ej: Taller 1, Examen Parcial)'),
            'descripcion': _('Instrucciones o descripción (Opcional)'),
            'fecha_publicacion': _('Fecha de Publicación/Asignación'),
            'fecha_entrega_limite': _('Fecha de Realización o Entrega Límite (Opcional)'),
            'material_adjunto': _('Material Adjunto (Opcional)'),
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
            'calificacion_obtenida': _('Nota Asignada'),
            'comentarios_docente': _('Comentarios o Retroalimentación'),
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
            'documento_identidad': _('Número de Documento'),
            'tipo_documento': _('Tipo de Documento'),
            'ocupacion': _('Ocupación'),
            'lugar_trabajo': _('Lugar de Trabajo / Empresa'),
            'direccion': _('Dirección de Residencia'),
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
            'dia_semana': _('Día de la Semana'),
            'hora_inicio': _('Disponible Desde'),
            'hora_fin': _('Disponible Hasta'),
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



class DisponibilidadOrientadorForm(forms.ModelForm):
    """
    Formulario para que el/la orientador(a) escolar defina un bloque de
    disponibilidad para atender familias. Espejo de DisponibilidadDocenteForm.
    """
    class Meta:
        model = DisponibilidadOrientador
        fields = ['dia_semana', 'hora_inicio', 'hora_fin']
        widgets = {
            'dia_semana': forms.Select(attrs={'class': 'form-select'}),
            'hora_inicio': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'hora_fin': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }
        labels = {
            'dia_semana': _('Día de la Semana'),
            'hora_inicio': _('Disponible Desde'),
            'hora_fin': _('Disponible Hasta'),
        }

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get('hora_inicio')
        fin = cleaned.get('hora_fin')
        if inicio and fin and fin <= inicio:
            self.add_error('hora_fin', _("La hora de fin debe ser posterior a la hora de inicio."))
        return cleaned


class GestionCitaOrientacionForm(forms.ModelForm):
    """
    Formulario para que el/la orientador(a) gestione una cita: actualizar su
    estado y registrar observaciones y acuerdos tras la reunión.
    """
    class Meta:
        model = CitaOrientacion
        fields = ['estado', 'observaciones_orientador', 'acuerdos_compromisos']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observaciones_orientador': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'acuerdos_compromisos': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SeguimientoOrientacionForm(forms.ModelForm):
    """Registro de una atención/seguimiento psicosocial del orientador."""
    class Meta:
        model = SeguimientoOrientacion
        fields = ['fecha', 'motivo', 'descripcion', 'acuerdos', 'remision',
                  'requiere_seguimiento', 'proxima_cita']
        widgets = {
            'fecha': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'motivo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Relato de la atención (confidencial)…'}),
            'acuerdos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'remision': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'EPS, ICBF, comisaría de familia, etc. (si aplica)'}),
            'requiere_seguimiento': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'proxima_cita': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'fecha': _('Fecha de la atención'),
            'motivo': _('Motivo'),
            'descripcion': _('Relato / observaciones (confidencial)'),
            'acuerdos': _('Acuerdos y recomendaciones'),
            'remision': _('Remisión a entidad externa'),
            'requiere_seguimiento': _('Requiere seguimiento'),
            'proxima_cita': _('Próxima cita / seguimiento'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']


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
            'enunciado': _('Texto o enunciado de la pregunta'),
            'tipo': _('Tipo de Pregunta'),
            'orden': _('Orden de aparición'),
            'duracion_minutos': _('Duración para esta pregunta (minutos)'),
            'numero_intentos_permitidos': _('Intentos permitidos para esta pregunta'),
        }
        help_texts = {
            'duracion_minutos': _('Dejar en blanco si no hay límite de tiempo.'),
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
        label=_("Fecha de Publicación")
    )

    fecha_entrega_limite = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date'},
            format='%Y-%m-%d'
        ),
        input_formats=['%Y-%m-%d', '%d/%m/%Y'],
        label=_("Fecha Límite de Entrega (Opcional)")
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
            'fecha_publicacion': _('Fecha de Publicación'),
            'fecha_entrega_limite': _('Fecha Límite de Entrega (Opcional)'),
            'duracion_minutos': _('Duración en Minutos (Opcional)'),
            'numero_intentos_permitidos': _('Número de Intentos Permitidos'),
        }
        
        # Textos de ayuda para guiar al docente
        help_texts = {
            'duracion_minutos': _('Dejar en blanco si no hay límite de tiempo.'),
            'numero_intentos_permitidos': _('Por defecto se sugieren 5 intentos (etapa escolar); máximo 20.'),
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
            'nombre': _('Nombre o Número del Aula'),
            'tipo': _('Tipo de Aula'),
            'capacidad': _('Capacidad de Estudiantes'),
            'ubicacion': _('Ubicación (Ej: Edificio A, Piso 2)'),
            'recursos': _('Recursos Disponibles (Ej: Proyector, Pizarra)'),
            'institucion': _('Institución a la que pertenece'),
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
                self.fields['institucion'].disabled = True

class AreaAcademicaForm(forms.ModelForm):
    materias = forms.ModelMultipleChoiceField(
        queryset=Materia.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'id': 'materias_disponibles', 'class': 'form-control', 'size': 10})
    )

    class Meta:
        model = AreaAcademica
        fields = ['nombre', 'orden', 'institucion', 'materias']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'orden': _('Orden de aparición'),
        }
        help_texts = {
            'orden': _('Menor número = aparece primero. Ej: 1, 2, 3…'),
        }

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if request and not request.user.is_superuser:
            self.fields['institucion'].initial = request.user.institucion_asociada
            self.fields['institucion'].disabled = True
            self.fields['institucion'].widget = forms.HiddenInput()
            self.fields['materias'].queryset = Materia.objects.filter(
                institucion=request.user.institucion_asociada
            )
        else:
            self.fields['materias'].queryset = Materia.objects.all()          

class DimensionDesarrolloForm(forms.ModelForm):
    """
    Formulario para crear y editar las Dimensiones de Desarrollo de Preescolar.
    """
    class Meta:
        model = DimensionDesarrollo
        fields = ['nombre', 'descripcion', 'orden', 'materias']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cognitiva, Comunicativa'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'orden': forms.NumberInput(attrs={'class': 'form-control'}),
            'materias': forms.CheckboxSelectMultiple(),
        }
        labels = {
            'nombre': _('Nombre de la Dimensión'),
            'descripcion': _('Descripción (Opcional)'),
            'orden': _('Orden de Aparición'),
            'materias': _('Materias asociadas (Opcional)'),
        }
        help_texts = {
            'orden': _('Un número menor aparecerá primero en la lista y en los reportes.'),
            'materias': _('Materias que aportan a esta dimensión del desarrollo.'),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['materias'].required = False
        if user is not None and getattr(user, 'institucion_asociada', None) is not None:
            self.fields['materias'].queryset = Materia.objects.filter(
                institucion=user.institucion_asociada
            ).order_by('nombre_materia')

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
            'grado': _('Grado'),
            'materia': _('Materia (opcional)'),
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

        # La materia es opcional (no todos los colegios la usan); el grado sí
        # es obligatorio para poder ubicar el logro en la lista por grado.
        self.fields['materia'].required = False
        self.fields['grado'].required = True

class TicketSoporteForm(forms.ModelForm):
    class Meta:
        model = TicketSoporte
        fields = ['titulo', 'descripcion', 'prioridad']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 6}),
        }
        labels = {
            'titulo': _('Asunto o Título Corto'),
            'descripcion': _('Por favor, describe el problema con el mayor detalle posible'),
            'prioridad': _('Nivel de Prioridad'),
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
            'mensaje': _('Tu Respuesta'),
            'adjunto': _('Adjuntar un archivo (Opcional)'),
        }                 

class PlaneacionClaseForm(forms.ModelForm):
    """
    Formulario para que el docente defina los parámetros de la planeación
    que se enviarán a la IA.
    """
    # Sobrescribimos el campo 'curso' para filtrarlo por el docente actual
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.none(), # El queryset se llenará en la vista
        label=_("Curso y Materia"),
        empty_label=_("--- Selecciona un curso ---")
    )

    class Meta:
        model = PlaneacionClase
        fields = ['titulo', 'curso', 'metodologia', 'duracion_clases']
        labels = {
            'titulo': _('¿Cuál es el tema principal o nombre de la unidad?'),
            'metodologia': _('¿Qué metodología de enseñanza prefieres usar?'),
            'duracion_clases': _('¿En cuántas clases quieres desarrollar este tema?'),
        }
        help_texts = {
            'titulo': _('Ej: "El Sistema Solar", "Introducción a las Fracciones", "El Renacimiento".'),
            'duracion_clases': _('La IA generará un plan detallado para este número de clases.'),
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
            'tema_tratado': _('Tema Tratado en la Clase'),
            'resumen_clase': _('Resumen y Actividades Realizadas'),
            'archivo_adjunto': _('Adjuntar un nuevo archivo (opcional)'),
        }                

class CandidatoForm(forms.ModelForm):
    """
    Formulario para registrar un estudiante como candidato en una elección.
    """
    # Hacemos que el campo 'estudiante' sea un selector con buscador para facilidad de uso.
    estudiante = forms.ModelChoiceField(
        queryset=Estudiante.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}), # Puedes añadir 'select2' si usas esa librería
        label=_("Estudiante Candidato")
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
            'first_name': _('Nombres'),
            'last_name': _('Apellidos'),
            'email': _('Correo Electrónico'),
            'rol': _('Rol en la Plataforma'),
            'is_active': _('¿Cuenta Activa?'),
        }
        help_texts = {
            'is_active': _('Desmarca esta casilla para desactivar la cuenta del usuario sin eliminarla.')
        }

class UserPasswordChangeForm(forms.Form):
    """
    Formulario dedicado para cambiar la contraseña de un usuario.
    """
    new_password1 = forms.CharField(
        label=_("Nueva Contraseña"),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )
    new_password2 = forms.CharField(
        label=_("Confirmar Nueva Contraseña"),
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False,
    )

    def clean_new_password2(self):
        password_1 = self.cleaned_data.get("new_password1")
        password_2 = self.cleaned_data.get("new_password2")
        if password_1 and password_2 and password_1 != password_2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password_2            

# ── Restablecimiento de contraseña con la cuenta Brevo/SMTP de cada colegio ──
import logging as _logging

from django.contrib.auth.forms import PasswordResetForm as _PasswordResetForm
from django.template import loader as _loader
from django.utils.html import escape as _escape

_logger_reset = _logging.getLogger(__name__)


class HaluPasswordResetForm(_PasswordResetForm):
    """Igual al PasswordResetForm de Django, pero envía el correo con las
    credenciales que la institución del usuario YA TIENE configuradas (su
    propia cuenta Brevo o su propio SMTP, vía
    admisiones.utils.enviar_correo_dinamico) en vez del EMAIL_BACKEND global.

    Así, cada colegio que configure su cuenta Brevo la usa para todo lo que
    envíe la plataforma en su nombre — restablecimiento de contraseña
    incluido — sin variables de entorno nuevas y sin tocar ni consumir el
    plan de ninguna otra institución.

    REGLA INNEGOCIABLE: NUNCA se usa un respaldo/cuenta compartida entre
    instituciones (ni BREVO_API_KEY global, ni ninguna otra credencial
    "de sistema"). El correo de un usuario siempre se envía con las
    credenciales de SU PROPIA institución (institucion.brevo_api_key /
    SMTP propio). Si su institución no tiene nada configurado, el correo
    simplemente no se envía (se registra en el log) — jamás se usa una
    cuenta ajena. Ver CLAUDE.md.

    Si el usuario no tiene institución asociada (ej. un superusuario), se
    usa el envío estándar de Django (EMAIL_BACKEND global de la
    plataforma, que no es de ninguna institución) — nunca el respaldo
    Brevo compartido.

    Importante: un fallo de entrega (ej. SMTP bloqueado en el hosting) NUNCA
    debe tumbar esta vista — además de ser mala experiencia, el flujo de
    reseteo de contraseña no debe revelar por un error si el correo existe o
    no. Todo intento de envío va protegido con try/except.
    """

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        user = context.get('user')
        institucion = getattr(user, 'institucion_asociada', None) if user else None

        subject = _loader.render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())  # el asunto no admite saltos de línea
        texto_plano = _loader.render_to_string(email_template_name, context)
        html_content = (
            _loader.render_to_string(html_email_template_name, context)
            if html_email_template_name else None
        )
        if html_content is None:
            html_content = (
                '<pre style="white-space:pre-wrap;font-family:inherit;">'
                + _escape(texto_plano) + '</pre>'
            )

        try:
            if institucion is not None:
                # SIEMPRE las credenciales de ESTA institución. enviar_correo_dinamico
                # ya prioriza institucion.brevo_api_key/SMTP propio; si la institución
                # no tiene nada configurado, no envía nada (no hay credencial ajena
                # de respaldo) — comportamiento correcto, no se toca.
                from admisiones.utils import enviar_correo_dinamico
                enviar_correo_dinamico(
                    institucion=institucion,
                    asunto=subject,
                    destinatarios=[to_email],
                    html_content=html_content,
                    texto_plano=texto_plano,
                )
                return

            # Usuario sin institución (ej. superusuario): no hay una cuenta de
            # colegio de la cual tomar credenciales, así que se usa el envío
            # estándar de Django (EMAIL_BACKEND de la plataforma). NUNCA se
            # intenta el respaldo Brevo compartido entre instituciones.
            super().send_mail(
                subject_template_name, email_template_name, context,
                from_email, to_email, html_email_template_name=html_email_template_name,
            )
        except Exception:
            _logger_reset.exception(
                "HaluPasswordResetForm: no se pudo enviar el correo de "
                "restablecimiento a %s.", to_email,
            )


# --- Validación de soportes subidos en el portal del estudiante ---
# Mismo criterio (extensión + tamaño + tipo MIME real por magic bytes) que
# admisiones._validar_archivo_documento, para no confiar solo en lo que el
# navegador declara.
JUSTIFICACION_INASISTENCIA_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
JUSTIFICACION_INASISTENCIA_EXTENSIONES = {"pdf", "jpg", "jpeg", "png", "webp", "doc", "docx"}
JUSTIFICACION_INASISTENCIA_MIME_REALES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class JustificacionInasistenciaForm(forms.ModelForm):
    class Meta:
        model = JustificacionInasistencia
        fields = ['fecha_inicio', 'fecha_fin', 'motivo', 'descripcion', 'documento_soporte']
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'motivo': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'fecha_inicio': _('Desde'),
            'fecha_fin': _('Hasta'),
            'motivo': _('Motivo'),
            'descripcion': _('Cuéntanos qué pasó (opcional si adjuntas soporte)'),
            'documento_soporte': _('Soporte (incapacidad médica, certificado, etc. — opcional)'),
        }

    def clean(self):
        cleaned = super().clean()
        inicio, fin = cleaned.get('fecha_inicio'), cleaned.get('fecha_fin')
        if inicio and fin and fin < inicio:
            raise ValidationError("La fecha 'Hasta' no puede ser anterior a la fecha 'Desde'.")
        return cleaned

    def clean_documento_soporte(self):
        archivo = self.cleaned_data.get('documento_soporte')
        if not archivo or not hasattr(archivo, 'size'):
            return archivo  # sin archivo nuevo, o no se modificó

        if archivo.size > JUSTIFICACION_INASISTENCIA_MAX_BYTES:
            raise ValidationError("El archivo supera el tamaño máximo permitido (10 MB).")

        nombre = (archivo.name or "").lower()
        extension = nombre.rsplit(".", 1)[-1] if "." in nombre else ""
        if extension not in JUSTIFICACION_INASISTENCIA_EXTENSIONES:
            raise ValidationError("Formato no permitido. Usa PDF, imagen (JPG/PNG/WEBP) o Word (DOC/DOCX).")

        try:
            import magic as _magic
            archivo.seek(0)
            header = archivo.read(2048)
            archivo.seek(0)
            mime_real = _magic.from_buffer(header, mime=True)
            if mime_real not in JUSTIFICACION_INASISTENCIA_MIME_REALES:
                raise ValidationError(
                    f"El contenido del archivo no corresponde al formato declarado. Tipo detectado: {mime_real}."
                )
        except ImportError:
            content_type = (getattr(archivo, "content_type", "") or "").lower()
            valid_mime_fallback = JUSTIFICACION_INASISTENCIA_MIME_REALES | {"application/octet-stream"}
            if content_type and content_type not in valid_mime_fallback:
                raise ValidationError("El tipo de archivo no coincide con los formatos permitidos.")
        return archivo
