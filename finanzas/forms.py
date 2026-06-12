# finanzas/forms.py
from django import forms
import datetime # Para el initial de fechas
from decimal import Decimal # Importar Decimal para validaciones y valores iniciales


# Importa los modelos financieros y otros necesarios desde sus ubicaciones correctas
# Asumo que todos los modelos financieros están en finanzas/models.py
from .models import (
    TipoConceptoPago, ConceptoPago, CuentaPorCobrarEstudiante, PagoRegistrado,
    InstitucionEducativa, TipoGasto,  # <-- AÑADE ESTA IMPORTACIÓN
    CategoriaGasto, # Si InstitucionEducativa se gestiona desde finanzas/models.py
)
# Estudiante y PeriodoAcademico se importan desde gestion_academica.models
from gestion_academica.models import Estudiante, PeriodoAcademico, Grado, NivelEscolaridad

from .models import CategoriaGasto, Proveedor, Gasto, Descuento, CuentaContable


def _conceptos_pago_orden_por_nivel(qs):
    """Orden homogéneo con el listado de finanzas: primero nivel (orden), luego nombre."""
    from django.db.models import F, OrderBy

    return qs.select_related('nivel_escolaridad').order_by(
        OrderBy(F('nivel_escolaridad__orden'), descending=False, nulls_last=True),
        'nivel_escolaridad__nombre',
        'nombre_concepto',
    )


# --- Formularios de Finanzas ---

class ConfiguracionPagoForm(forms.ModelForm):
    """
    Formulario para que el administrador de una institución pueda
    configurar sus propias credenciales de Mercado Pago.
    """
    class Meta:
        model = InstitucionEducativa
        fields = [
            'mp_public_key_test', 'mp_access_token_test',
            'mp_public_key_prod', 'mp_access_token_prod',
            'mp_modo_produccion'
        ]
        labels = {
            'mp_public_key_test': 'Public Key de Prueba',
            'mp_access_token_test': 'Access Token de Prueba',
            'mp_public_key_prod': 'Public Key de Producción',
            'mp_access_token_prod': 'Access Token de Producción',
            'mp_modo_produccion': 'Activar Pagos Reales (Modo Producción)'
        }
        help_texts = {
            'mp_public_key_test': 'Empieza con APP_USR-... La encuentras en tu dashboard de Mercado Pago > Credenciales de Prueba.',
            'mp_access_token_test': 'Empieza con TEST-... La encuentras en tu dashboard de Mercado Pago > Credenciales de Prueba.',
            'mp_public_key_prod': 'Empieza con APP_USR-... La encuentras en tu dashboard de Mercado Pago > Credenciales de Producción.',
            'mp_access_token_prod': 'Empieza con PROD-... La encuentras en tu dashboard de Mercado Pago > Credenciales de Producción.',
            'mp_modo_produccion': 'Marca esta casilla para usar las credenciales de Producción y procesar pagos reales. Desmarcada, usará las de Prueba.'
        }
        widgets = {
            'mp_public_key_test': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_access_token_test': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_public_key_prod': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_access_token_prod': forms.TextInput(attrs={'class': 'form-control'}),
            'mp_modo_produccion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
# =========================================================================
# FIN: NUEVO FORMULARIO
# =========================================================================

class TipoConceptoPagoForm(forms.ModelForm):
    class Meta:
        model = TipoConceptoPago
        fields = ['nombre', 'descripcion', 'institucion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mensualidad, Matrícula, Transporte'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción breve del tipo de concepto...'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre del Tipo de Concepto de Pago',
            'descripcion': 'Descripción (Opcional)',
            'institucion': 'Institución',
        }
    
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        user = getattr(request, 'user', None)
        if user is not None and user.is_superuser:
            self.fields['institucion'].queryset = InstitucionEducativa.objects.all().order_by('nombre')
        else:
            # Los usuarios de colegio nunca eligen institución: la inyecta la
            # vista desde request.user.institucion_asociada (form_valid).
            self.fields.pop('institucion', None)


class ConceptoPagoForm(forms.ModelForm):
    """Misma información que el admin de Django: se persiste en los mismos campos del modelo."""

    class Meta:
        model = ConceptoPago
        fields = [
            'institucion',
            'nivel_escolaridad',
            'tipo_concepto',
            'nombre_concepto',
            'descripcion_detallada',
            'valor',
            'periodo_academico_aplicable',
            'fecha_vencimiento_general',
            'cuenta_contable',
            'permite_mora',
            'porcentaje_mora_mensual',
            'es_pago_inscripcion',
            'es_pago_matricula',
            'es_pago_pension',
            'es_solicitable_por_egresado',
            'automatico',
        ]
        widgets = {
            'institucion': forms.Select(attrs={'class': 'form-select'}),
            'nivel_escolaridad': forms.Select(attrs={'class': 'form-select'}),
            'tipo_concepto': forms.Select(attrs={'class': 'form-select'}),
            'nombre_concepto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Pensión marzo 2026'}),
            'descripcion_detallada': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'periodo_academico_aplicable': forms.Select(attrs={'class': 'form-select'}),
            'fecha_vencimiento_general': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
            'permite_mora': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'porcentaje_mora_mensual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'es_pago_inscripcion': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_pago_matricula': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_pago_pension': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_solicitable_por_egresado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'automatico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'institucion': 'Institución',
            'nivel_escolaridad': 'Nivel de escolaridad',
            'tipo_concepto': 'Tipo de concepto',
            'nombre_concepto': 'Nombre del concepto',
            'descripcion_detallada': 'Descripción (opcional)',
            'valor': 'Valor estándar',
            'periodo_academico_aplicable': 'Periodo académico (opcional)',
            'fecha_vencimiento_general': 'Fecha de vencimiento general (opcional)',
            'cuenta_contable': 'Cuenta contable PUC (ingreso)',
            'permite_mora': 'Permite generar mora',
            'porcentaje_mora_mensual': 'Porcentaje de mora mensual (%)',
            'es_pago_inscripcion': 'Es el concepto de inscripción (admisiones)',
            'es_pago_matricula': 'Es el concepto de matrícula',
            'es_pago_pension': 'Es pensión / mensualidad',
            'es_solicitable_por_egresado': 'Solicitable desde portal de egresados',
            'automatico': 'Generar automáticamente al registrar estudiante',
        }

    def __init__(self, *args, **kwargs):
        self._request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        inst = None
        if self.instance.pk and self.instance.institucion_id:
            inst = self.instance.institucion
        elif self._request and not self._request.user.is_superuser:
            inst = getattr(self._request.user, 'institucion_asociada', None)

        if inst:
            self.fields['tipo_concepto'].queryset = (
                TipoConceptoPago.objects.filter(institucion=inst).order_by('nombre')
            )
            self.fields['nivel_escolaridad'].queryset = (
                NivelEscolaridad.objects.filter(institucion=inst).order_by('orden', 'nombre')
            )
            self.fields['periodo_academico_aplicable'].queryset = (
                PeriodoAcademico.objects.filter(institucion=inst).order_by('-año_escolar', '-fecha_inicio')
            )
            self.fields['cuenta_contable'].queryset = (
                CuentaContable.objects.filter(institucion=inst, tipo='INGRESO').order_by('codigo')
            )
            self.fields['institucion'].queryset = InstitucionEducativa.objects.filter(pk=inst.pk)
            self.fields['institucion'].initial = inst
            self.fields['institucion'].widget = forms.HiddenInput()
        else:
            self.fields['tipo_concepto'].queryset = TipoConceptoPago.objects.all().order_by('institucion__nombre', 'nombre')
            self.fields['nivel_escolaridad'].queryset = NivelEscolaridad.objects.all().order_by('institucion__nombre', 'orden', 'nombre')
            self.fields['periodo_academico_aplicable'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
            self.fields['cuenta_contable'].queryset = CuentaContable.objects.filter(tipo='INGRESO').order_by('institucion__nombre', 'codigo')
            self.fields['institucion'].queryset = InstitucionEducativa.objects.all().order_by('nombre')

    def clean(self):
        cleaned = super().clean()
        inst = cleaned.get('institucion')
        nivel = cleaned.get('nivel_escolaridad')
        tipo = cleaned.get('tipo_concepto')
        if inst and nivel and nivel.institucion_id != inst.pk:
            raise forms.ValidationError({
                'nivel_escolaridad': 'El nivel debe pertenecer a la misma institución seleccionada.',
            })
        if inst and tipo and tipo.institucion_id != inst.pk:
            raise forms.ValidationError({
                'tipo_concepto': 'El tipo de concepto debe pertenecer a la misma institución.',
            })
        cc = cleaned.get('cuenta_contable')
        if inst and cc and cc.institucion_id != inst.pk:
            raise forms.ValidationError({
                'cuenta_contable': 'La cuenta PUC debe ser de la misma institución.',
            })
        pa = cleaned.get('periodo_academico_aplicable')
        if inst and pa and pa.institucion_id != inst.pk:
            raise forms.ValidationError({
                'periodo_academico_aplicable': 'El periodo académico debe ser de la misma institución.',
            })
        return cleaned


class CuentaPorCobrarEstudianteForm(forms.ModelForm):
    # Asegúrate de que el queryset de concepto_pago se filtre por institución si es necesario
    concepto_pago = forms.ModelChoiceField(
        queryset=_conceptos_pago_orden_por_nivel(ConceptoPago.objects.all()),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_concepto_pago_selector'}),
        label="Concepto de Pago"
    )

    class Meta:
        model = CuentaPorCobrarEstudiante
        exclude = [
            'estudiante', 'concepto_pago', 'monto_asignado', 
            'fecha_vencimiento_especifica', 'observaciones_internas', 'institucion'
        ]
        widgets = {
            'estudiante': forms.Select(attrs={'class': 'form-select'}),
            'monto_asignado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Monto a cobrar'}),
            'fecha_vencimiento_especifica': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                # initial=datetime.date.today() + datetime.timedelta(days=30) # No es necesario aquí si se usa en __init__
            ),
            'observaciones_internas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Notas internas sobre esta cuenta...'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'estudiante': 'Estudiante',
            'monto_asignado': 'Monto Asignado al Estudiante',
            'fecha_vencimiento_especifica': 'Fecha de Vencimiento Específica',
            'observaciones_internas': 'Observaciones Internas (Opcional)',
            'institucion': 'Institución',
        }
        

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        user = getattr(request, 'user', None)
        institucion = getattr(user, 'institucion_asociada', None) if user else None

        # La institución nunca se elige en el formulario: la inyecta la vista
        # desde request.user.institucion_asociada en form_valid.
        self.fields.pop('institucion', None)

        # En edición, la institución de referencia es la de la cuenta existente.
        if self.instance.pk and self.instance.institucion_id:
            institucion = self.instance.institucion

        estudiantes = Estudiante.objects.select_related('usuario').order_by(
            'usuario__last_name', 'usuario__first_name'
        )
        conceptos = ConceptoPago.objects.all()
        if user is None or not user.is_superuser:
            if institucion is not None:
                estudiantes = estudiantes.filter(institucion=institucion)
                conceptos = conceptos.filter(institucion=institucion)
            else:
                estudiantes = estudiantes.none()
                conceptos = conceptos.none()
        elif institucion is not None:
            conceptos = conceptos.filter(institucion=institucion)

        if 'estudiante' in self.fields:
            self.fields['estudiante'].queryset = estudiantes
        self.fields['concepto_pago'].queryset = _conceptos_pago_orden_por_nivel(conceptos)

        # Si es un nuevo formulario (no una instancia existente), establece la fecha inicial
        if not self.instance.pk and 'fecha_vencimiento_especifica' in self.fields:
            self.fields['fecha_vencimiento_especifica'].initial = datetime.date.today() + datetime.timedelta(days=30)


    def clean(self):
        cleaned_data = super().clean()
        estudiante = cleaned_data.get("estudiante")
        concepto_pago = cleaned_data.get("concepto_pago")
        institucion = cleaned_data.get("institucion") # Obtén la institución del cleaned_data

        if estudiante and concepto_pago and institucion:
            # Asegúrate de que la institución usada en la consulta sea la del formulario
            query = CuentaPorCobrarEstudiante.objects.filter(
                estudiante=estudiante, 
                concepto_pago=concepto_pago,
                institucion=institucion # Usa la institución del formulario
            )
            if self.instance and self.instance.pk:
                query = query.exclude(pk=self.instance.pk)
            if query.exists():
                raise forms.ValidationError(
                    f"El estudiante '{estudiante}' ya tiene una cuenta por cobrar pendiente o registrada para el concepto '{concepto_pago}' en esta institución. "
                    "Verifique las cuentas existentes o edite la cuenta correspondiente."
                )
        return cleaned_data


class PagoForm(forms.ModelForm):
    # Campo extra (no modelo) para notificar corrección al editar
    notificar_cambios = forms.BooleanField(
        required=False,
        label="Notificar cambios por correo al acudiente/estudiante",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = PagoRegistrado
        fields = [
            'fecha_pago',
            'valor_pagado',
            'metodo_pago',
            'referencia_transaccion',
            'observacion',
        ]
        widgets = {
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pagado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'referencia_transaccion': forms.TextInput(attrs={'class': 'form-control'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.cuenta = kwargs.pop('cuenta', None)
        super().__init__(*args, **kwargs)
        # Al crear un pago nuevo: sugerir saldo pendiente y ocultar checkbox de notificación
        if not (self.instance and self.instance.pk):
            self.fields.pop('notificar_cambios')
            if self.cuenta:
                self.fields['valor_pagado'].initial = self.cuenta.saldo_pendiente
                self.fields['valor_pagado'].help_text = f"Saldo pendiente sugerido: ${self.cuenta.saldo_pendiente:.2f}"

        # Si estamos creando un pago nuevo y tenemos la cuenta, sugerimos el saldo pendiente
        if self.cuenta and not self.instance.pk:
            self.fields['valor_pagado'].initial = self.cuenta.saldo_pendiente
            self.fields['valor_pagado'].help_text = f"Saldo pendiente sugerido: ${self.cuenta.saldo_pendiente:.2f}"

    def clean_valor_pagado(self):
        valor_pagado = self.cleaned_data.get('valor_pagado')

        if not valor_pagado or valor_pagado <= 0:
            raise forms.ValidationError("El valor a pagar debe ser un número mayor que cero.")
        
        if self.cuenta:
            # Lógica de validación para no pagar más del saldo
            saldo_maximo = self.cuenta.saldo_pendiente
            if self.instance and self.instance.pk:  # Si estamos editando un pago existente
                saldo_maximo += self.instance.valor_pagado
            
            if valor_pagado > saldo_maximo:
                raise forms.ValidationError(f"El valor a pagar no puede exceder el saldo de ${saldo_maximo:.2f}")

        return valor_pagado
    
class TipoGastoForm(forms.ModelForm):
    class Meta:
        model = TipoGasto
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# --- MODIFICACIÓN DEL FORMULARIO DE CATEGORÍA DE GASTO ---
class CategoriaGastoForm(forms.ModelForm):
    class Meta:
        model = CategoriaGasto
        # Ahora incluimos el campo 'tipo_gasto'
        fields = ['tipo_gasto', 'nombre', 'cuenta_contable']
        widgets = {
            'tipo_gasto': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
        }

    # Para que el queryset del campo 'tipo_gasto' solo muestre los de la institución actual
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            institucion = user.institucion_asociada
            self.fields['tipo_gasto'].queryset = TipoGasto.objects.filter(institucion=institucion)

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'nit_o_cedula', 'telefono', 'email']

    def clean_nombre(self):
        return (self.cleaned_data.get('nombre') or '').strip()

    def clean_nit_o_cedula(self):
        return (self.cleaned_data.get('nit_o_cedula') or '').strip()

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        return email

class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = ['descripcion', 'monto', 'fecha_gasto', 'categoria', 'proveedor', 'comprobante']
        widgets = {
            'fecha_gasto': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Filtra los desplegables para que solo muestren datos de la institución correcta
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            institucion = user.institucion_asociada
            self.fields['categoria'].queryset = CategoriaGasto.objects.filter(institucion=institucion)
            self.fields['proveedor'].queryset = Proveedor.objects.filter(institucion=institucion)

class DescuentoForm(forms.ModelForm):
    class Meta:
        model = Descuento
        fields = ['nombre', 'tipo', 'valor', 'conceptos_aplicables', 'activo']
        widgets = {
            'conceptos_aplicables': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser:
            # Filtra los conceptos para que solo se muestren los de la institución
            self.fields['conceptos_aplicables'].queryset = _conceptos_pago_orden_por_nivel(
                ConceptoPago.objects.filter(institucion=user.institucion_asociada)
            )
        else:
            self.fields['conceptos_aplicables'].queryset = _conceptos_pago_orden_por_nivel(
                ConceptoPago.objects.all()
            )              

class FacturacionMasivaForm(forms.Form):
    concepto_pago = forms.ModelChoiceField(
        queryset=ConceptoPago.objects.none(),
        label="1. Selecciona el Concepto a Cobrar",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg mb-3'})
    )

    fecha_vencimiento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg mb-3'}),
        label="2. Selecciona la Fecha de Vencimiento"
    )

    toda_la_institucion = forms.BooleanField(
        required=False,
        label="Aplicar a TODOS los estudiantes de la institución",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    grados = forms.ModelMultipleChoiceField(
        queryset=Grado.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="O, aplica solo a los siguientes grados:",
        required=False
    )

    notificar_correo = forms.BooleanField(
        required=False,
        initial=True,
        label="Notificar a acudientes y estudiantes por correo electrónico",
        help_text="Se enviará un aviso de cobro con el detalle del cobro y el enlace de pago (Mercado Pago) a cada acudiente o estudiante registrado.",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        # Sacamos el 'user' que le pasamos desde la vista
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario está logueado y tiene una institución, filtramos los querysets
        if user and hasattr(user, 'institucion_asociada'):
            institucion = user.institucion_asociada
            if institucion:
                self.fields['concepto_pago'].queryset = _conceptos_pago_orden_por_nivel(
                    ConceptoPago.objects.filter(institucion=institucion)
                )
                self.fields['grados'].queryset = Grado.objects.filter(institucion=institucion).order_by('nombre')

    def clean(self):
        cleaned_data = super().clean()
        grados = cleaned_data.get('grados')
        toda_la_institucion = cleaned_data.get('toda_la_institucion')

        # Validación: El usuario debe elegir al menos una opción de a quién facturar
        if not grados and not toda_la_institucion:
            raise forms.ValidationError(
                "Debes seleccionar al menos un grado o marcar la opción 'Aplicar a toda la institución'."
            )
        return cleaned_data

# finanzas/forms.py

class ExportacionContableForm(forms.Form):
    TIPO_TRANSACCION_CHOICES = (
        ('TODOS', 'Ingresos y Gastos'),
        ('INGRESOS', 'Solo Ingresos'),
        ('GASTOS', 'Solo Gastos'),
    )
    
    fecha_inicio = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Fecha de Inicio"
    )
    fecha_fin = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Fecha de Fin"
    )
    tipo_transaccion = forms.ChoiceField(
        choices=TIPO_TRANSACCION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Tipo de Transacciones a Exportar"
    )
    FORMATO_CHOICES = (
        ('XLSX', 'Excel (.xlsx) — hojas Resumen y Movimientos'),
        ('CSV', 'CSV UTF-8 (separador ;) — resumen y movimientos en un archivo'),
        (
            'PDF',
            'PDF — carátula de exportación (resumen para archivo físico / contador; sin detalle de movimientos)',
        ),
    )
    formato = forms.ChoiceField(
        choices=FORMATO_CHOICES,
        initial='XLSX',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Formato de archivo",
    )
    periodo_academico = forms.ModelChoiceField(
        queryset=PeriodoAcademico.objects.none(),
        required=False,
        label="Periodo académico (solo ingresos)",
        help_text="Opcional. Filtra los ingresos a los pagos cuya fecha esté dentro del rango del periodo seleccionado. Los gastos no se filtran por periodo.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def _validar_anio_fecha(self, campo):
        from datetime import date as date_type
        fecha = self.cleaned_data.get(campo)
        if not fecha:
            return fecha
        # Chrome/Edge en español envía año de 2 dígitos como 0026 cuando el usuario escribe 26.
        # Lo corregimos transparentemente: 0–99 → 2000–2099.
        if fecha.year < 100:
            fecha = date_type(fecha.year + 2000, fecha.month, fecha.day)
        if not (2000 <= fecha.year <= 2100):
            raise forms.ValidationError(
                f"El año {fecha.year} no es válido. Ingrese una fecha entre 2000 y 2100."
            )
        return fecha

    def clean_fecha_inicio(self):
        return self._validar_anio_fecha("fecha_inicio")

    def clean_fecha_fin(self):
        return self._validar_anio_fecha("fecha_fin")

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")
        return cleaned_data

    def __init__(self, *args, inst=None, **kwargs):
        super().__init__(*args, **kwargs)
        if inst:
            qs = PeriodoAcademico.objects.filter(institucion=inst).order_by(
                "-año_escolar", "-fecha_inicio"
            )
            self.fields["periodo_academico"].queryset = qs
            # Etiqueta con fechas para que el usuario vea qué rango abarca cada periodo
            self.fields["periodo_academico"].label_from_instance = (
                lambda per: f"{per.nombre} ({per.año_escolar})  [{per.fecha_inicio.strftime('%d/%m')} – {per.fecha_fin.strftime('%d/%m/%Y')}]"
            )


class LibroDiarioContableForm(forms.Form):
    """Filtros para consultar el libro diario en pantalla (mismos criterios que exportación)."""

    TIPO_TRANSACCION_CHOICES = (
        ("TODOS", "Ingresos y Gastos"),
        ("INGRESOS", "Solo Ingresos"),
        ("GASTOS", "Solo Gastos"),
    )

    fecha_inicio = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Fecha de inicio",
    )
    fecha_fin = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Fecha de fin",
    )
    tipo_transaccion = forms.ChoiceField(
        choices=TIPO_TRANSACCION_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Tipo de movimientos",
    )
    periodo_academico = forms.ModelChoiceField(
        queryset=PeriodoAcademico.objects.none(),
        required=False,
        label="Periodo académico (solo ingresos)",
        help_text="Opcional. Filtra ingresos por el periodo aplicable del concepto de cobro.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get("fecha_inicio")
        fecha_fin = cleaned_data.get("fecha_fin")
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")
        return cleaned_data

    def __init__(self, *args, inst=None, **kwargs):
        super().__init__(*args, **kwargs)
        if inst:
            qs = PeriodoAcademico.objects.filter(institucion=inst).order_by(
                "-año_escolar", "-fecha_inicio"
            )
            self.fields["periodo_academico"].queryset = qs
            self.fields["periodo_academico"].label_from_instance = (
                lambda per: f"{per.nombre} ({per.año_escolar})  [{per.fecha_inicio.strftime('%d/%m')} – {per.fecha_fin.strftime('%d/%m/%Y')}]"
            )


class CuentaContableForm(forms.ModelForm):
    """
    Formulario para crear y editar Cuentas Contables (PUC).
    """
    class Meta:
        model = CuentaContable
        fields = ['codigo', 'nombre', 'tipo']
        widgets = {
            'nombre': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        institucion = kwargs.pop('institucion', None)
        super().__init__(*args, **kwargs)
        # El código es de solo lectura al editar (no al crear)
        if self.instance and self.instance.pk:
            self.fields['codigo'].widget.attrs['readonly'] = True
    