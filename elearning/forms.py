from django import forms
from django.core.exceptions import ValidationError

from finanzas.models import ConceptoPago

from .models import Curso, Modulo, Material, Evaluacion, Pregunta, Opcion


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = [
            "institucion",
            "nombre",
            "descripcion",
            "imagen_portada",
            "precio",
            "concepto_pago_asociado",
            "duracion_horas",
            "publicado",
        ]
        widgets = {
            "institucion": forms.Select(attrs={"class": "form-select"}),
            "descripcion": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "precio": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "concepto_pago_asociado": forms.Select(attrs={"class": "form-select"}),
            "duracion_horas": forms.NumberInput(attrs={"class": "form-control"}),
            "imagen_portada": forms.FileInput(attrs={"class": "form-control"}),
            "publicado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_superuser:
            self.fields.pop("institucion", None)

        inst = None
        if self.instance and self.instance.pk and self.instance.institucion_id:
            inst = self.instance.institucion
        elif self.user and getattr(self.user, "institucion_asociada_id", None):
            inst = self.user.institucion_asociada
        if inst is not None and "concepto_pago_asociado" in self.fields:
            self.fields["concepto_pago_asociado"].queryset = ConceptoPago.objects.filter(
                institucion=inst
            ).order_by("nombre_concepto")
            self.fields["concepto_pago_asociado"].required = False

    def clean(self):
        data = super().clean()
        precio = data.get("precio")
        concepto = data.get("concepto_pago_asociado")
        if precio and precio > 0 and not concepto:
            raise ValidationError(
                {
                    "concepto_pago_asociado": "Si la oferta tiene precio, debe asociar un concepto de pago de Finanzas."
                }
            )
        return data


class ModuloForm(forms.ModelForm):
    class Meta:
        model = Modulo
        fields = ["titulo", "descripcion", "orden"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
        }


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ["titulo", "tipo", "archivo", "enlace", "orden"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "archivo": forms.FileInput(attrs={"class": "form-control"}),
            "enlace": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://youtube.com/..."}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
        }


class EvaluacionForm(forms.ModelForm):
    class Meta:
        model = Evaluacion
        fields = ["titulo", "porcentaje_aprobacion", "intentos_permitidos"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "form-control"}),
            "porcentaje_aprobacion": forms.NumberInput(attrs={"class": "form-control"}),
            "intentos_permitidos": forms.NumberInput(attrs={"class": "form-control"}),
        }


class PreguntaForm(forms.ModelForm):
    class Meta:
        model = Pregunta
        fields = ["texto", "puntos"]
        widgets = {
            "texto": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "puntos": forms.NumberInput(attrs={"class": "form-control"}),
        }


class OpcionForm(forms.ModelForm):
    class Meta:
        model = Opcion
        fields = ["texto", "es_correcta"]
        widgets = {
            "texto": forms.TextInput(attrs={"class": "form-control"}),
            "es_correcta": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
