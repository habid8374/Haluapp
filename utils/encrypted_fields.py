"""
utils/encrypted_fields.py
Campo de Django que cifra valores sensibles con Fernet (AES-128-CBC + HMAC-SHA256)
antes de guardarlos en la BD y los descifra automáticamente al leerlos.

Requiere en settings.py:
    FERNET_KEY = os.environ.get('FERNET_KEY')  # 32 bytes, base64-url-safe

Para generar una clave nueva (ejecutar una sola vez):
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from django.db import models
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    from django.conf import settings
    key = getattr(settings, 'FERNET_KEY', None)
    if not key:
        raise ImproperlyConfigured(
            "FERNET_KEY no está definido en settings.py. "
            "Genera una clave con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class EncryptedCharField(models.TextField):
    """
    Almacena texto cifrado con Fernet. Transparente para el código de la aplicación:
    leer devuelve el valor original, escribir almacena el cifrado.

    Compatibilidad hacia atrás: si un valor no puede descifrarse (dato en texto
    plano heredado), se devuelve como está para que el admin pueda actualizarlo.
    La próxima vez que se guarde el registro, quedará cifrado.
    """

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except (InvalidToken, Exception):
            # Dato en plaintext anterior al cifrado → devolver sin modificar
            return value

    def get_prep_value(self, value):
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs
