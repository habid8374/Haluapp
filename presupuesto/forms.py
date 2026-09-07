from django import forms

from finanzas.models import Proveedor

from .models import (
    CDP,
    RP,
    Apropiacion,
    CatalogoGeneralCuentas,
    ConceptoRetencion,
    FuenteFinanciacion,
    ModificacionPresupuestal,
    Obligacion,
    OrdenDePago,
    PresupuestoIngreso,
    RetencionAplicada,
    RubroPresupuestalGasto,
    RubroPresupuestalIngreso,
    VigenciaFiscal,
)
from .widgets import CategoriaCPCWidget


class _InstitucionScopedFormMixin:
    """Recibe `institucion` por kwarg y filtra los FK relevantes a ella —
    mismo patrón que ya usan los formularios de gestion_academica."""

    fk_institucion_fields = ()

    def __init__(self, *args, institucion=None, **kwargs):
        self.institucion = institucion
        super().__init__(*args, **kwargs)
        if institucion is not None:
            for field_name in self.fk_institucion_fields:
                if field_name in self.fields:
                    self.fields[field_name].queryset = self.fields[field_name].queryset.filter(institucion=institucion)


class VigenciaFiscalForm(_InstitucionScopedFormMixin, forms.ModelForm):
    class Meta:
        model = VigenciaFiscal
        fields = ['anio']
        widgets = {'anio': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000, 'max': 2100})}


class RubroPresupuestalIngresoForm(_InstitucionScopedFormMixin, forms.ModelForm):
    # tipo_recurso es del catálogo CHIP GLOBAL (sin institución) — su
    # queryset se filtra manualmente abajo, no con fk_institucion_fields
    # (mismo criterio que cuenta_puc_pasivo en ConceptoRetencionForm).
    fk_institucion_fields = ('rubro_padre',)

    class Meta:
        model = RubroPresupuestalIngreso
        fields = ['codigo', 'nombre', 'tipo_recurso', 'rubro_padre', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo_recurso': forms.Select(attrs={'class': 'form-select'}),
            'rubro_padre': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_recurso'].queryset = FuenteFinanciacion.objects.all()
        self.fields['tipo_recurso'].required = True


class RubroPresupuestalGastoForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('rubro_padre',)

    class Meta:
        model = RubroPresupuestalGasto
        fields = ['codigo', 'nombre', 'tipo', 'rubro_padre', 'cuenta_cgc_gasto', 'activo']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'rubro_padre': forms.Select(attrs={'class': 'form-select'}),
            'cuenta_cgc_gasto': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_cgc_gasto'].queryset = CatalogoGeneralCuentas.objects.filter(activo=True, permite_movimientos=True)


class PresupuestoIngresoForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('vigencia', 'rubro')

    class Meta:
        model = PresupuestoIngreso
        fields = ['vigencia', 'rubro', 'valor_inicial']
        widgets = {
            'vigencia': forms.Select(attrs={'class': 'form-select'}),
            'rubro': forms.Select(attrs={'class': 'form-select'}),
            'valor_inicial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ApropiacionForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('vigencia', 'rubro')

    class Meta:
        model = Apropiacion
        fields = ['vigencia', 'rubro', 'valor_inicial']
        widgets = {
            'vigencia': forms.Select(attrs={'class': 'form-select'}),
            'rubro': forms.Select(attrs={'class': 'form-select'}),
            'valor_inicial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class ModificacionPresupuestalForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('apropiacion', 'apropiacion_destino')

    class Meta:
        model = ModificacionPresupuestal
        fields = ['apropiacion', 'tipo', 'valor', 'apropiacion_destino', 'acto_administrativo', 'soporte']
        widgets = {
            'apropiacion': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'apropiacion_destino': forms.Select(attrs={'class': 'form-select'}),
            'acto_administrativo': forms.TextInput(attrs={'class': 'form-control'}),
            'soporte': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class CDPForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('apropiacion',)

    class Meta:
        model = CDP
        fields = ['apropiacion', 'valor', 'objeto']
        widgets = {
            'apropiacion': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'objeto': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.institucion is not None:
            self.fields['apropiacion'].queryset = self.fields['apropiacion'].queryset.filter(
                vigencia__estado='ABIERTA'
            )


class RPForm(_InstitucionScopedFormMixin, forms.ModelForm):
    # categoria_cpc es del catálogo CPC del DANE, GLOBAL (sin institución) —
    # se busca por texto, no se filtra por institucion.
    fk_institucion_fields = ('cdp', 'tercero')

    class Meta:
        model = RP
        fields = ['cdp', 'tercero', 'objeto_contrato', 'categoria_cpc', 'valor']
        widgets = {
            'cdp': forms.Select(attrs={'class': 'form-select'}),
            'tercero': forms.Select(attrs={'class': 'form-select'}),
            'objeto_contrato': forms.TextInput(attrs={'class': 'form-control'}),
            'categoria_cpc': CategoriaCPCWidget(),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.institucion is not None:
            self.fields['cdp'].queryset = self.fields['cdp'].queryset.filter(estado=CDP.Estado.VIGENTE)
            self.fields['tercero'].queryset = Proveedor.objects.filter(institucion=self.institucion)


class ObligacionForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('rp',)

    class Meta:
        model = Obligacion
        fields = ['rp', 'valor', 'soporte_recibido_satisfaccion']
        widgets = {
            'rp': forms.Select(attrs={'class': 'form-select'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'soporte_recibido_satisfaccion': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.institucion is not None:
            self.fields['rp'].queryset = self.fields['rp'].queryset.filter(estado=RP.Estado.VIGENTE)


class OrdenDePagoForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('obligacion',)

    class Meta:
        model = OrdenDePago
        fields = ['obligacion']
        widgets = {
            'obligacion': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.institucion is not None:
            self.fields['obligacion'].queryset = self.fields['obligacion'].queryset.filter(estado=Obligacion.Estado.VIGENTE)


class RetencionAplicadaForm(_InstitucionScopedFormMixin, forms.ModelForm):
    fk_institucion_fields = ('concepto',)

    class Meta:
        model = RetencionAplicada
        fields = ['concepto', 'base_gravable']
        widgets = {
            'concepto': forms.Select(attrs={'class': 'form-select'}),
            'base_gravable': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.institucion is not None:
            self.fields['concepto'].queryset = ConceptoRetencion.objects.filter(institucion=self.institucion, activo=True)


class ConceptoRetencionForm(_InstitucionScopedFormMixin, forms.ModelForm):
    # cuenta_puc_pasivo es del catálogo CGC GLOBAL (sin institución) — su
    # queryset se filtra manualmente abajo, no con fk_institucion_fields.

    class Meta:
        model = ConceptoRetencion
        fields = ['tipo', 'nombre', 'tarifa_porcentaje', 'cuenta_puc_pasivo', 'activo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'tarifa_porcentaje': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'cuenta_puc_pasivo': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_puc_pasivo'].queryset = CatalogoGeneralCuentas.objects.filter(activo=True, permite_movimientos=True)


class GenerarComprobanteForm(forms.Form):
    cuenta_bancos = forms.ModelChoiceField(
        queryset=CatalogoGeneralCuentas.objects.filter(activo=True, permite_movimientos=True),
        label='Cuenta de Bancos/Caja desde la que se paga',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='La Tesorería/Bancos por institución llega en la Fase 3 — por ahora se elige aquí la cuenta CGC.',
    )
