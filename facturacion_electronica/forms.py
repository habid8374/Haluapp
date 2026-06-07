from django import forms

from .models import ConfiguracionFactus


class ConfiguracionFactusForm(forms.ModelForm):
    """Formulario de credenciales Factus para el admin de la institución.

    El campo ``activo`` NO está aquí: lo controla el propietario de la
    plataforma (tras el pago del adicional).
    """

    class Meta:
        model = ConfiguracionFactus
        fields = [
            "ambiente",
            "client_id",
            "client_secret",
            "username",
            "password",
            "numbering_range_id",
            "numbering_range_id_nota_credito",
            "numbering_range_id_nota_debito",
            "emision_automatica",
        ]
        widgets = {
            "ambiente": forms.Select(attrs={"class": "form-select"}),
            "numbering_range_id_nota_credito": forms.NumberInput(attrs={"class": "form-control"}),
            "numbering_range_id_nota_debito": forms.NumberInput(attrs={"class": "form-control"}),
            "emision_automatica": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "client_id": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "client_secret": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "username": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "password": forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}, render_value=True),
            "numbering_range_id": forms.NumberInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "ambiente": "Usa Pruebas (Sandbox) mientras validas la integración.",
            "numbering_range_id": "ID del rango de numeración autorizado por la DIAN (lo obtienes del panel/endpoint de Factus).",
        }
