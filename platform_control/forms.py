from django import forms


class SuperAdminLoginForm(forms.Form):
    username = forms.CharField(
        label="Usuario",
        widget=forms.TextInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Usuario administrador",
            "autofocus": True,
            "autocomplete": "username",
        }),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Contraseña",
            "autocomplete": "current-password",
        }),
        strip=False,
    )
    master_password = forms.CharField(
        label="Clave Maestra",
        widget=forms.PasswordInput(attrs={
            "class": "form-control form-control-lg",
            "placeholder": "Clave maestra de la plataforma",
            "autocomplete": "off",
        }),
        strip=False,
    )
