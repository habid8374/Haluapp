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
from gestion_academica.models import Estudiante, PeriodoAcademico, Grado

from .models import CategoriaGasto, Proveedor, Gasto, Descuento, CuentaContable


# --- Formularios de Finanzas ---

class MasterPasswordForm(forms.Form):
        master_password = forms.CharField(
            label="Clave Maestra de Super-Administrador",
            widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Introduce la clave secreta'}),
            strip=False
        )

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
        super().__init__(*args, **kwargs)
        # Asegúrate de que el queryset de institución sea el correcto
        self.fields['institucion'].queryset = InstitucionEducativa.objects.all().order_by('nombre')


class ConceptoPagoForm(forms.ModelForm):
    class Meta:
        model = ConceptoPago
        # El campo 'monto_estandar' se renombró a 'valor' en finanzas/models.py, ajusta aquí:
        fields = [
            'tipo_concepto',
            'nombre_concepto', 
            'descripcion_detallada',         
            'valor', # Usar 'valor'
            'periodo_academico_aplicable',
            'fecha_vencimiento_general',
            'automatico',
            'institucion'
        ]
        widgets = {
            'tipo_concepto': forms.Select(attrs={'class': 'form-select'}),
            'nombre_concepto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Mensualidad Abril 2025'}),
            'descripcion_detallada': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detalles adicionales sobre este cobro...'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej: 150000.00'}), # Usar 'valor'
            'periodo_academico_aplicable': forms.Select(attrs={'class': 'form-select'}),
            'fecha_vencimiento_general': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'automatico': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'institucion': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'tipo_concepto': 'Tipo de Concepto',
            'nombre_concepto': 'Nombre Específico del Concepto',
            'descripcion_detallada': 'Descripción Detallada (Opcional)',
            'valor': 'Monto Estándar', # Etiqueta para 'valor'
            'periodo_academico_aplicable': 'Periodo Académico Aplicable (Opcional)',
            'fecha_vencimiento_general': 'Fecha de Vencimiento General (Opcional)',
            'automatico': '¿Generar automáticamente al registrar estudiante?',
            'institucion': 'Institución',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_concepto'].queryset = TipoConceptoPago.objects.all().order_by('nombre')
        if 'periodo_academico_aplicable' in self.fields:
            self.fields['periodo_academico_aplicable'].queryset = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
        self.fields['institucion'].queryset = InstitucionEducativa.objects.all().order_by('nombre')


class CuentaPorCobrarEstudianteForm(forms.ModelForm):
    # Asegúrate de que el queryset de concepto_pago se filtre por institución si es necesario
    concepto_pago = forms.ModelChoiceField(
        queryset=ConceptoPago.objects.all().order_by('nombre_concepto'),
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
        super().__init__(*args, **kwargs)
        self.fields['estudiante'].queryset = Estudiante.objects.select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')
        
        # Si es un nuevo formulario (no una instancia existente), establece la fecha inicial
        if not self.instance.pk:
            self.fields['fecha_vencimiento_especifica'].initial = datetime.date.today() + datetime.timedelta(days=30)
        
        self.fields['institucion'].queryset = InstitucionEducativa.objects.all().order_by('nombre')

        # Si el usuario actual no es superusuario, filtra las opciones de institución
        if 'request' in kwargs and not kwargs['request'].user.is_superuser:
            if hasattr(kwargs['request'].user, 'institucion_asociada') and kwargs['request'].user.institucion_asociada:
                self.fields['institucion'].queryset = InstitucionEducativa.objects.filter(pk=kwargs['request'].user.institucion_asociada.pk)
                self.fields['institucion'].initial = kwargs['request'].user.institucion_asociada
                self.fields['institucion'].widget.attrs['disabled'] = True # Deshabilita el campo
            else:
                self.fields['institucion'].queryset = InstitucionEducativa.objects.none()
        
        # Filtra los conceptos de pago por institución si la instancia ya tiene una institución
        if self.instance and self.instance.institucion:
            self.fields['concepto_pago'].queryset = ConceptoPago.objects.filter(institucion=self.instance.institucion).order_by('nombre_concepto')
        # O si el formulario se inicializa con una institución a través del request
        elif 'request' in kwargs and hasattr(kwargs['request'].user, 'institucion_asociada') and kwargs['request'].user.institucion_asociada:
            self.fields['concepto_pago'].queryset = ConceptoPago.objects.filter(institucion=kwargs['request'].user.institucion_asociada).order_by('nombre_concepto')


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
    class Meta:
        model = PagoRegistrado
        # En lugar de 'exclude', definimos explícitamente los campos que el usuario debe ver.
        # 'institucion', 'cuenta', 'estudiante' y 'registrado_por' se asignan en la vista.
        fields = [
            'fecha_pago', 
            'valor_pagado', 
            'metodo_pago', 
            'referencia_transaccion', 
            'observacion'
        ]
        widgets = {
            'fecha_pago': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'valor_pagado': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'referencia_transaccion': forms.TextInput(attrs={'class': 'form-control'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # Recibimos la 'cuenta' desde la vista para validaciones y valores iniciales
        self.cuenta = kwargs.pop('cuenta', None)
        super().__init__(*args, **kwargs)

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
            self.fields['conceptos_aplicables'].queryset = ConceptoPago.objects.filter(
                institucion=user.institucion_asociada
            )              

class FacturacionMasivaForm(forms.Form):
    # Campo para seleccionar el concepto que se va a cobrar
    concepto_pago = forms.ModelChoiceField(
        queryset=ConceptoPago.objects.none(), # Se llenará dinámicamente
        label="1. Selecciona el Concepto a Cobrar",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg mb-3'})
    )
    
    # Campo para la fecha de vencimiento
    fecha_vencimiento = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-lg mb-3'}),
        label="2. Selecciona la Fecha de Vencimiento"
    )

    # Checkbox para aplicar a todos
    toda_la_institucion = forms.BooleanField(
        required=False,
        label="Aplicar a TODOS los estudiantes de la institución",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    # Campo para seleccionar uno o varios grados
    grados = forms.ModelMultipleChoiceField(
        queryset=Grado.objects.none(), # Se llenará dinámicamente
        widget=forms.CheckboxSelectMultiple,
        label="O, aplica solo a los siguientes grados:",
        required=False
    )

    def __init__(self, *args, **kwargs):
        # Sacamos el 'user' que le pasamos desde la vista
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Si el usuario está logueado y tiene una institución, filtramos los querysets
        if user and hasattr(user, 'institucion_asociada'):
            institucion = user.institucion_asociada
            if institucion:
                self.fields['concepto_pago'].queryset = ConceptoPago.objects.filter(institucion=institucion).order_by('nombre_concepto')
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

class CuentaContableForm(forms.ModelForm):
    """
    Formulario para crear y editar Cuentas Contables (PUC).
    """
    class Meta:
        model = CuentaContable
        # ✅ Se usan solo los campos que existen en tu modelo
        fields = [
            'codigo', 
            'nombre'
        ]
        widgets = {
            'nombre': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        # Esta lógica es importante para la multi-institución, pero se simplifica
        institucion = kwargs.pop('institucion', None)
        super().__init__(*args, **kwargs)

        # Hacemos que el campo de código sea de solo lectura al editar
        if self.instance and self.instance.pk:
            self.fields['codigo'].widget.attrs['readonly'] = True
    