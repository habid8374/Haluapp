# gestion_academica/forms.py
from django import forms
from .models import (
    Usuario, Estudiante, Grado, Docente, Familiar,
    Materia, PeriodoAcademico, Curso, DirectorCurso,
    EsquemaCalificacion, TipoActividad, ActividadCalificable, Calificacion,
    PlanCurricular, Deber, EntregaDeber, MencionReconocimiento, ArchivoPlanAcademico,
    ConfiguracionInstitucion, TipoConceptoPago, ConceptoPago, 
    CuentaPorCobrarEstudiante, PagoRegistrado, InstitucionEducativa,
    Noticia # Asegúrate de importar Noticia
)
import datetime

class RegistroInicialForm(forms.ModelForm):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = InstitucionEducativa
        fields = ['nombre', 'nit', 'direccion', 'telefono', 'correo', 'logo']

class GradoForm(forms.ModelForm):
    class Meta:
        model = Grado
        fields = ['nombre', 'nivel']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Primero A'}),
            'nivel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Primaria'}),
        }
        labels = {
            'nombre': 'Nombre del Grado',
            'nivel': 'Nivel Educativo (Opcional)',
        }

class PagoRegistradoForm(forms.ModelForm):
    class Meta:
        model = PagoRegistrado
        fields = ['fecha_pago', 'valor_pagado', 'observacion']
        widgets = {
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pagado': forms.NumberInput(attrs={'class': 'form-control'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'fecha_pago': 'Fecha del Pago',
            'valor_pagado': 'Valor Pagado',
            'observacion': 'Observación',
        }   

class PagoForm(forms.ModelForm):
    class Meta:
        model = PagoRegistrado
        fields = ['valor_pagado', 'observacion']
        widgets = {
            'valor_pagado': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese el monto a pagar',
                'min': '0',
                'step': '0.01',
            }),
            'observacion': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese una observación (opcional)',
                'rows': 3
            }),
        }
        labels = {
            'monto_pagado': 'Monto a Pagar',
            'observacion': 'Observación',
        }             

class UsuarioEstudianteForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=True, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label="Correo Electrónico (Opcional)", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(label="Confirmar Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']
        widgets = {'username': forms.TextInput(attrs={'class': 'form-control'})}
        labels = {'username': 'Nombre de Usuario (para login)'}

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Por favor, elige otro.")
        return username

    def clean_confirm_password(self):
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return confirm_password
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.rol = 'estudiante'
        if commit:
            user.save()
        return user

class EstudianteForm(forms.ModelForm):
    valor_matricula = forms.DecimalField(
        required=False,
        label="Valor Matrícula",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100000'})
    )
    valor_mensualidad = forms.DecimalField(
        required=False,
        label="Valor Mensualidad",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 80000'})
    )

    class Meta:
        model = Estudiante
        fields = ['documento_identidad', 'codigo_estudiante', 'fecha_nacimiento', 'direccion', 'grado_actual', 'valor_matricula', 'valor_mensualidad']
        widgets = {
            'documento_identidad': forms.TextInput(attrs={'class': 'form-control'}),
            'codigo_estudiante': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_nacimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'grado_actual': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'documento_identidad': 'Documento de Identidad',
            'codigo_estudiante': 'Código de Estudiante (Opcional)',
            'fecha_nacimiento': 'Fecha de Nacimiento (Opcional)',
            'direccion': 'Dirección (Opcional)',
            'grado_actual': 'Grado Actual (Opcional)',
        }


class UsuarioEstudianteUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=True, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label="Correo Electrónico (Opcional)", widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {'username': forms.TextInput(attrs={'class': 'form-control'})}
        labels = {'username': 'Nombre de Usuario (para login)'}

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Usuario.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso por otra cuenta. Por favor, elige otro.")
        return username
    
class UsuarioDocenteForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=True, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label="Correo Electrónico (Opcional)", widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(label="Confirmar Contraseña", widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']
        widgets = {'username': forms.TextInput(attrs={'class': 'form-control'})}
        labels = {'username': 'Nombre de Usuario (para login)'}

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Usuario.objects.filter(username=username).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso. Por favor, elige otro.")
        return username

    def clean_confirm_password(self):
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return confirm_password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.rol = 'docente'
        if commit:
            user.save()
        return user

class DocenteForm(forms.ModelForm):
    class Meta:
        model = Docente
        fields = ['codigo_docente', 'especialidad']
        widgets = {
            'codigo_docente': forms.TextInput(attrs={'class': 'form-control'}),
            'especialidad': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'codigo_docente': 'Código de Docente (Opcional)',
            'especialidad': 'Especialidad Principal (Opcional)',
        }

class UsuarioDocenteUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="Nombres", widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, required=True, label="Apellidos", widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=False, label="Correo Electrónico (Opcional)", widget=forms.EmailInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Usuario
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {'username': forms.TextInput(attrs={'class': 'form-control'})}
        labels = {'username': 'Nombre de Usuario (para login)'}

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if Usuario.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Este nombre de usuario ya está en uso por otra cuenta. Por favor, elige otro.")
        return username

class MateriaForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ['nombre_materia', 'codigo_materia', 'descripcion']
        widgets = {
            'nombre_materia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Matemáticas I'}),
            'codigo_materia': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: MAT101'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Breve descripción de la materia...'}),
        }
        labels = {
            'nombre_materia': 'Nombre de la Materia',
            'codigo_materia': 'Código de Materia (Opcional)',
            'descripcion': 'Descripción (Opcional)',
        }

class PeriodoAcademicoForm(forms.ModelForm):
    class Meta:
        model = PeriodoAcademico
        fields = ['nombre', 'año_escolar', 'fecha_inicio', 'fecha_fin', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Año Escolar 2025'}),
            'año_escolar': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2025'}),
            'fecha_inicio': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nombre': 'Nombre del Periodo',
            'año_escolar': 'Año Escolar',
            'fecha_inicio': 'Fecha de Inicio',
            'fecha_fin': 'Fecha de Fin',
            'activo': 'Marcar como Periodo Activo Actual',
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise forms.ValidationError("La fecha de fin no puede ser anterior a la fecha de inicio.")
        return cleaned_data

class CursoForm(forms.ModelForm):
    docentes_asignados = forms.ModelMultipleChoiceField(
        queryset=Docente.objects.all().order_by('usuario__last_name', 'usuario__first_name'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        required=False,
        label="Docentes Asignados"
    )
    class Meta:
        model = Curso
        fields = ['materia', 'grado', 'periodo_academico', 'docentes_asignados']
        widgets = {
            'materia': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {'materia': 'Materia', 'grado': 'Grado', 'periodo_academico': 'Periodo Académico'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['materia'].queryset = Materia.objects.all().order_by('nombre_materia')
        self.fields['grado'].queryset = Grado.objects.all().order_by('nombre')
        self.fields['periodo_academico'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

class DirectorCursoForm(forms.ModelForm):
    class Meta:
        model = DirectorCurso
        fields = ['docente', 'grado', 'periodo_academico']
        widgets = {
            'docente': forms.Select(attrs={'class': 'form-select'}),
            'grado': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {'docente': 'Docente Director', 'grado': 'Grado a Dirigir', 'periodo_academico': 'Periodo Académico'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['docente'].queryset = Docente.objects.all().order_by('usuario__last_name', 'usuario__first_name')
        self.fields['grado'].queryset = Grado.objects.all().order_by('nombre')
        self.fields['periodo_academico'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    def clean(self):
        cleaned_data = super().clean()
        grado = cleaned_data.get("grado")
        periodo_academico = cleaned_data.get("periodo_academico")
        if grado and periodo_academico:
            qs = DirectorCurso.objects.filter(grado=grado, periodo_academico=periodo_academico)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"El grado '{grado}' ya tiene un director asignado para el periodo '{periodo_academico}'. Solo puede haber un director por grado en cada periodo.")
        return cleaned_data

class EsquemaCalificacionForm(forms.ModelForm):
    class Meta:
        model = EsquemaCalificacion
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Numérico (0-10)'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción detallada del esquema...'}),
        }
        labels = {'nombre': 'Nombre del Esquema de Calificación', 'descripcion': 'Descripción (Opcional)'}

class TipoActividadForm(forms.ModelForm):
    class Meta:
        model = TipoActividad
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Examen Final'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción del tipo de actividad...'}),
        }
        labels = {'nombre': 'Nombre del Tipo de Actividad', 'descripcion': 'Descripción (Opcional)'}

class ActividadCalificableForm(forms.ModelForm):
    class Meta:
        model = ActividadCalificable
        fields = ['curso', 'tipo_actividad', 'titulo', 'descripcion', 'fecha_publicacion', 'fecha_entrega_limite', 'porcentaje_en_periodo', 'material_adjunto']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'tipo_actividad': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Primer Examen de Álgebra'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalles de la actividad, temas a cubrir, etc.'}),
            'fecha_publicacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega_limite': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'porcentaje_en_periodo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'material_adjunto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'curso': 'Curso al que pertenece la actividad', 'tipo_actividad': 'Tipo de Actividad',
            'titulo': 'Título de la Actividad', 'descripcion': 'Descripción Detallada (Opcional)',
            'fecha_publicacion': 'Fecha de Publicación/Asignación', 'fecha_entrega_limite': 'Fecha Límite de Entrega (Opcional)',
            'porcentaje_en_periodo': 'Porcentaje en la Nota del Periodo (%) (Opcional)', 'material_adjunto': 'Material Adjunto (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.select_related('materia', 'grado', 'periodo_academico').order_by('-periodo_academico__año_escolar', '-periodo_academico__fecha_inicio', 'grado__nombre', 'materia__nombre_materia')
        self.fields['tipo_actividad'].queryset = TipoActividad.objects.all().order_by('nombre')

    def clean_fecha_entrega_limite(self):
        fecha_publicacion = self.cleaned_data.get('fecha_publicacion')
        fecha_entrega_limite = self.cleaned_data.get('fecha_entrega_limite')
        if fecha_publicacion and fecha_entrega_limite and fecha_entrega_limite < fecha_publicacion:
            raise forms.ValidationError("La fecha límite de entrega no puede ser anterior a la fecha de publicación.")
        return fecha_entrega_limite

    def clean_porcentaje_en_periodo(self):
        porcentaje = self.cleaned_data.get('porcentaje_en_periodo')
        if porcentaje is not None and (porcentaje < 0 or porcentaje > 100):
            raise forms.ValidationError("El porcentaje debe estar entre 0 y 100.")
        return porcentaje

class CalificacionForm(forms.ModelForm):
    class Meta:
        model = Calificacion
        fields = ['valor_numerico', 'valor_cualitativo', 'observaciones']
        widgets = {
            'valor_numerico': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 4.5 o 85.00'}),
            'valor_cualitativo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Aprobado, Sobresaliente'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Comentarios adicionales sobre el desempeño...'}),
        }
        labels = {
            'valor_numerico': 'Calificación Numérica (Opcional)',
            'valor_cualitativo': 'Calificación Cualitativa (Opcional)',
            'observaciones': 'Observaciones (Opcional)',
        }

    def clean(self):
        cleaned_data = super().clean()
        valor_numerico = cleaned_data.get('valor_numerico')
        valor_cualitativo = cleaned_data.get('valor_cualitativo')
        if valor_numerico is None and not valor_cualitativo:
            raise forms.ValidationError("Debes ingresar al menos un valor de calificación (numérico o cualitativo).")
        return cleaned_data

class DeberForm(forms.ModelForm):
    class Meta:
        model = Deber
        fields = ['curso', 'titulo', 'descripcion', 'fecha_asignacion', 'fecha_entrega', 'material_adjunto']
        widgets = {
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Investigación sobre la Célula'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Instrucciones detalladas para el deber...'}),
            'fecha_asignacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'fecha_entrega': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'material_adjunto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'curso': 'Curso para el cual es el deber', 'titulo': 'Título del Deber',
            'descripcion': 'Descripción / Instrucciones (Opcional)', 'fecha_asignacion': 'Fecha de Asignación',
            'fecha_entrega': 'Fecha Límite de Entrega', 'material_adjunto': 'Adjuntar Material de Apoyo (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['curso'].queryset = Curso.objects.select_related('materia', 'grado', 'periodo_academico').order_by('-periodo_academico__año_escolar', '-periodo_academico__fecha_inicio', 'grado__nombre', 'materia__nombre_materia')

    def clean(self):
        cleaned_data = super().clean()
        fecha_asignacion = cleaned_data.get("fecha_asignacion")
        fecha_entrega = cleaned_data.get("fecha_entrega")
        if fecha_asignacion and fecha_entrega and fecha_entrega < fecha_asignacion:
            raise forms.ValidationError("La fecha límite de entrega no puede ser anterior a la fecha de asignación.")
        return cleaned_data

class EntregaDeberForm(forms.ModelForm):
    class Meta:
        model = EntregaDeber
        fields = ['archivo_adjunto_estudiante', 'comentarios_estudiante']
        widgets = {
            'archivo_adjunto_estudiante': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'comentarios_estudiante': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Añade comentarios para tu entrega aquí...'}),
        }
        labels = {
            'archivo_adjunto_estudiante': 'Adjuntar Archivo (Opcional)',
            'comentarios_estudiante': 'Comentarios Adicionales (Opcional)',
        }

    def clean(self):
        cleaned_data = super().clean()
        archivo = cleaned_data.get('archivo_adjunto_estudiante')
        comentarios = cleaned_data.get('comentarios_estudiante')
        if not archivo and not comentarios:
            raise forms.ValidationError("Debes adjuntar un archivo o escribir un comentario para realizar la entrega.")
        return cleaned_data

class PlanCurricularForm(forms.ModelForm):
    class Meta:
        model = PlanCurricular
        fields = [
            'nombre', 'descripcion', 'documento_adjunto', 
            'grado_asociado', 'materia_asociada', 'periodo_academico_asociado',
            'fecha_publicacion'
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Plan Curricular Anual de Matemáticas'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Objetivos, contenidos principales, metodología...'}),
            'documento_adjunto': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'grado_asociado': forms.Select(attrs={'class': 'form-select'}),
            'materia_asociada': forms.Select(attrs={'class': 'form-select'}),
            'periodo_academico_asociado': forms.Select(attrs={'class': 'form-select'}),
            'fecha_publicacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'nombre': 'Nombre del Plan Curricular', 'descripcion': 'Descripción Detallada (Opcional)',
            'documento_adjunto': 'Adjuntar Documento del Plan (Opcional)', 'grado_asociado': 'Grado Asociado (Opcional)',
            'materia_asociada': 'Materia Asociada (Opcional)', 'periodo_academico_asociado': 'Periodo Académico de Aplicación (Opcional)',
            'fecha_publicacion': 'Fecha de Publicación o Vigencia',
        }
        help_texts = {
            'grado_asociado': 'Si se selecciona, el material será específico para este grado.',
            'materia_asociada': 'Si se selecciona, el material será general para esta materia.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'grado_asociado' in self.fields:
            self.fields['grado_asociado'].queryset = Grado.objects.all().order_by('nombre')
        if 'materia_asociada' in self.fields:
            self.fields['materia_asociada'].queryset = Materia.objects.all().order_by('nombre_materia')
        if 'periodo_academico_asociado' in self.fields:
            self.fields['periodo_academico_asociado'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

class MencionReconocimientoForm(forms.ModelForm):
    class Meta:
        model = MencionReconocimiento
        fields = [
            'estudiante', 'tipo', 'descripcion', 'fecha_otorgamiento',
            'curso', 'periodo', 'otorgado_por'
        ]
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'curso': forms.Select(attrs={'class': 'form-select'}),
            'periodo': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cuadro de Honor'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detalles del reconocimiento otorgado...'}),
            'fecha_otorgamiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'otorgado_por': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'estudiante': 'Estudiante Reconocido', 'curso': 'Curso Asociado (Opcional)',
            'periodo': 'Periodo Académico Asociado (Opcional)', 'tipo': 'Tipo de Mención o Reconocimiento',
            'descripcion': 'Descripción Detallada', 'fecha_otorgamiento': 'Fecha de Otorgamiento',
            'otorgado_por': 'Otorgado/Registrado por (Docente - Opcional)',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = Estudiante.objects.select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')
        if 'curso' in self.fields:
             self.fields['curso'].queryset = Curso.objects.select_related('materia', 'grado', 'periodo_academico').order_by('-periodo_academico__año_escolar', 'grado__nombre', 'materia__nombre_materia')
        if 'periodo' in self.fields:
            self.fields['periodo'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
        if 'otorgado_por' in self.fields:
            self.fields['otorgado_por'].queryset = Docente.objects.select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')
            self.fields['otorgado_por'].required = False

class ArchivoPlanAcademicoForm(forms.ModelForm):
    class Meta:
        model = ArchivoPlanAcademico
        fields = [
            'nombre_archivo_descriptivo', 'archivo', 'descripcion', 
            'tipo_documento', 'curso_asociado', 'materia_asociada'
        ]
        widgets = {
            'nombre_archivo_descriptivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Guía de Estudio Unidad 1'}),
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Breve descripción del contenido del archivo...'}),
            'tipo_documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: PDF, Documento Word, Presentación'}),
            'curso_asociado': forms.Select(attrs={'class': 'form-select'}),
            'materia_asociada': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre_archivo_descriptivo': 'Nombre Descriptivo del Archivo', 'archivo': 'Seleccionar Archivo',
            'descripcion': 'Descripción (Opcional)', 'tipo_documento': 'Tipo de Documento (Opcional)',
            'curso_asociado': 'Asociar a un Curso Específico (Opcional)', 'materia_asociada': 'Asociar a una Materia en General (Opcional)',
        }
        help_texts = {
            'curso_asociado': 'Si se selecciona, el material será específico para este curso.',
            'materia_asociada': 'Si se selecciona, el material será general para esta materia.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'curso_asociado' in self.fields:
            self.fields['curso_asociado'].queryset = Curso.objects.select_related('materia', 'grado', 'periodo_academico').order_by('-periodo_academico__año_escolar', 'grado__nombre', 'materia__nombre_materia')
        if 'materia_asociada' in self.fields:
            self.fields['materia_asociada'].queryset = Materia.objects.all().order_by('nombre_materia')

class TipoConceptoPagoForm(forms.ModelForm):
    class Meta:
        model = TipoConceptoPago
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mensualidad, Matrícula, Transporte'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción breve del tipo de concepto...'}),
        }
        labels = {
            'nombre': 'Nombre del Tipo de Concepto de Pago',
            'descripcion': 'Descripción (Opcional)',
        }

class ConceptoPagoForm(forms.ModelForm):
    class Meta:
        model = ConceptoPago
        fields = [
            'tipo_concepto',
            'nombre_concepto', 
            'descripcion_detallada',         
            'monto_estandar',
            'periodo_academico_aplicable',
            'fecha_vencimiento_general',
            'automatico',  # 👈 Añadimos aquí
        ]
        widgets = {
            'tipo_concepto': forms.Select(attrs={'class': 'form-select'}),
            'nombre_concepto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mensualidad Abril 2025'}),
            'descripcion_detallada': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalles adicionales sobre este cobro...'}),
            'monto_estandar': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 150000.00'}),
            'periodo_academico_aplicable': forms.Select(attrs={'class': 'form-select'}),
            'fecha_vencimiento_general': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'automatico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),  # 👈 Widget para checkbox
        }
        labels = {
            'tipo_concepto': 'Tipo de Concepto',
            'nombre_concepto': 'Nombre Específico del Concepto',
            'descripcion_detallada': 'Descripción Detallada (Opcional)',
            'monto_estandar': 'Monto Estándar',
            'periodo_academico_aplicable': 'Periodo Académico Aplicable (Opcional)',
            'fecha_vencimiento_general': 'Fecha de Vencimiento General (Opcional)',
            'automatico': '¿Generar automáticamente al registrar estudiante?',  # 👈 Etiqueta personalizada
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_concepto'].queryset = TipoConceptoPago.objects.all().order_by('nombre')
        if 'periodo_academico_aplicable' in self.fields:
            self.fields['periodo_academico_aplicable'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

class NoticiaForm(forms.ModelForm): # <--- FORMULARIO PARA NOTICIA AÑADIDO
    class Meta:
        model = Noticia
        fields = ['titulo', 'contenido', 'imagen_destacada']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título atractivo para la noticia'}),
            'contenido': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Escribe el contenido completo aquí...'}),
            'imagen_destacada': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'titulo': 'Título',
            'contenido': 'Contenido',
            'imagen_destacada': 'Imagen Destacada (Opcional)',
        }

# Aquí faltarían los formularios para CuentaPorCobrarEstudiante y PagoRegistrado
# si también los vas a gestionar desde la interfaz pública.

class CuentaPorCobrarEstudianteForm(forms.ModelForm):
    # Campo para seleccionar el concepto y autocompletar el monto_asignado
    # Esto es una mejora, el monto_asignado también se puede editar manualmente.
    concepto_pago = forms.ModelChoiceField(
        queryset=ConceptoPago.objects.all().order_by('nombre_concepto'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_concepto_pago_selector'}), # Añadimos un ID para JS
        label="Concepto de Pago"
    )

    class Meta:
        model = CuentaPorCobrarEstudiante
        # 'monto_pagado' y 'estado' se manejarán principalmente por la lógica de registro de pagos y el método save() del modelo.
        # 'fecha_creacion' y 'ultima_modificacion' son automáticos.
        fields = [
            'estudiante', 'concepto_pago', 'monto_asignado', 
            'fecha_vencimiento_especifica', 'observaciones_internas'
            # 'estado' podría ser editable aquí si se quiere anular manualmente, pero es mejor con acciones.
        ]
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'monto_asignado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Monto a cobrar'}),
            'fecha_vencimiento_especifica': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                # default = datetime.date.today() + datetime.timedelta(days=30) # Ejemplo de default
            ),
            'observaciones_internas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas internas sobre esta cuenta...'}),
        }
        labels = {
            'estudiante': 'Estudiante',
            'monto_asignado': 'Monto Asignado al Estudiante',
            'fecha_vencimiento_especifica': 'Fecha de Vencimiento Específica',
            'observaciones_internas': 'Observaciones Internas (Opcional)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = Estudiante.objects.select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')
        
        # Si estamos editando y hay una instancia, el monto_asignado ya tiene valor.
        # Si estamos creando, podríamos querer que monto_asignado se llene dinámicamente
        # cuando se seleccione un concepto_pago. Esto se haría con JavaScript en la plantilla.
        # O, al guardar la vista, si monto_asignado no se llenó, tomar el monto_estandar del concepto.

        # Poner un valor por defecto para fecha_vencimiento_especifica si es una nueva instancia
        if not self.instance.pk: # Si es un objeto nuevo (no tiene clave primaria aún)
            self.fields['fecha_vencimiento_especifica'].initial = datetime.date.today() + datetime.timedelta(days=30)


    def clean(self):
        cleaned_data = super().clean()
        estudiante = cleaned_data.get("estudiante")
        concepto_pago = cleaned_data.get("concepto_pago")

        # Validar que no se duplique una cuenta por cobrar para el mismo estudiante y concepto
        # (excepto si estamos editando la misma instancia)
        if estudiante and concepto_pago:
            query = CuentaPorCobrarEstudiante.objects.filter(estudiante=estudiante, concepto_pago=concepto_pago)
            if self.instance and self.instance.pk: # Si es una edición
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise forms.ValidationError(
                    f"El estudiante '{estudiante}' ya tiene una cuenta por cobrar pendiente o registrada para el concepto '{concepto_pago}'. "
                    "Verifique las cuentas existentes o edite la cuenta correspondiente."
                )
        return cleaned_data