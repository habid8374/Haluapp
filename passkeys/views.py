"""
Endpoints WebAuthn (Passkeys) para registro de dispositivo e inicio de sesión
biométrico.

Flujo de REGISTRO (usuario ya autenticado):
  1) opciones_registro  -> genera challenge, lo guarda en sesión, devuelve opciones.
  2) verificar_registro -> valida la respuesta del autenticador y guarda la credencial.

Flujo de LOGIN (usuario anónimo):
  1) opciones_login   -> genera challenge de aserción (usernameless / passkey).
  2) verificar_login  -> valida la firma, identifica al usuario por la credencial
                         e inicia la sesión de Django.

La librería `webauthn` se importa de forma diferida: si no está instalada, solo
fallan estos endpoints (con un mensaje claro), no el resto del sitio.
"""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import CredencialWebAuthn

logger = logging.getLogger(__name__)


# ── Configuración RP (Relying Party) ─────────────────────────────────────────

def _rp_id():
    return getattr(settings, 'WEBAUTHN_RP_ID', 'app.haluplataform.com')


def _rp_name():
    return getattr(settings, 'WEBAUTHN_RP_NAME', 'Halu Plataforma Escolar')


def _origin():
    # Puede ser una lista de orígenes permitidos.
    return getattr(settings, 'WEBAUTHN_ORIGIN', 'https://app.haluplataform.com')


def _wa():
    """Importa la librería webauthn de forma diferida. Lanza RuntimeError claro
    si no está instalada."""
    try:
        import webauthn  # noqa
        from webauthn.helpers import base64url_to_bytes, bytes_to_base64url  # noqa
        from webauthn.helpers.structs import (  # noqa
            AuthenticatorSelectionCriteria, ResidentKeyRequirement,
            UserVerificationRequirement, PublicKeyCredentialDescriptor,
            AuthenticatorAttachment,
        )
        return webauthn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "El paquete 'webauthn' no está instalado. Agrega 'webauthn' a "
            "requirements.txt y vuelve a desplegar."
        ) from exc


def _error(mensaje, status=400):
    return JsonResponse({'ok': False, 'error': mensaje}, status=status)


# ── Página de gestión (usuario autenticado) ──────────────────────────────────

@login_required
def gestionar(request):
    credenciales = CredencialWebAuthn.objects.filter(usuario=request.user)
    return render(request, 'passkeys/gestionar.html', {
        'titulo_pagina': 'Ingreso con huella',
        'credenciales': credenciales,
        'soportado_servidor': _disponible(),
    })


def _disponible():
    try:
        _wa()
        return True
    except RuntimeError:
        return False


# ── Registro de dispositivo ──────────────────────────────────────────────────

@require_POST
@login_required
def opciones_registro(request):
    try:
        webauthn = _wa()
    except RuntimeError as e:
        return _error(str(e), status=503)
    from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, ResidentKeyRequirement,
        UserVerificationRequirement, PublicKeyCredentialDescriptor,
        AuthenticatorAttachment,
    )

    user = request.user
    existentes = [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
        for c in CredencialWebAuthn.objects.filter(usuario=user)
    ]
    opciones = webauthn.generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_id=str(user.pk).encode('utf-8'),
        user_name=(user.get_username() or getattr(user, 'email', '') or f'user{user.pk}'),
        user_display_name=(user.get_full_name() or user.get_username() or 'Usuario'),
        exclude_credentials=existentes,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            # REQUIRED: la credencial queda "descubrible" en el dispositivo, para
            # poder iniciar sesión sin escribir usuario ("Ingresar con huella").
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    # Guardamos el challenge (base64url) en la sesión para verificarlo luego.
    request.session['webauthn_reg_challenge'] = bytes_to_base64url(opciones.challenge)
    return HttpResponse(webauthn.options_to_json(opciones), content_type='application/json')


@require_POST
@login_required
def verificar_registro(request):
    try:
        webauthn = _wa()
    except RuntimeError as e:
        return _error(str(e), status=503)
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

    reto = request.session.pop('webauthn_reg_challenge', None)
    if not reto:
        return _error("No hay un registro en curso. Inténtalo de nuevo.")
    try:
        cuerpo = request.body.decode('utf-8')
        datos = json.loads(cuerpo)
    except (ValueError, UnicodeDecodeError):
        return _error("Datos inválidos.")

    try:
        verificacion = webauthn.verify_registration_response(
            credential=cuerpo,
            expected_challenge=base64url_to_bytes(reto),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=True,
        )
    except Exception as exc:
        logger.warning("WebAuthn registro fallido (user %s): %s", request.user.pk, exc)
        return _error("No se pudo verificar el dispositivo. Inténtalo de nuevo.")

    cred_id_b64 = bytes_to_base64url(verificacion.credential_id)
    if CredencialWebAuthn.objects.filter(credential_id=cred_id_b64).exists():
        return _error("Este dispositivo ya estaba registrado.")

    transportes = ''
    try:
        transportes = ','.join(datos.get('response', {}).get('transports', []) or [])
    except Exception:
        pass
    nombre = (datos.get('nombre_dispositivo') or 'Mi dispositivo')[:120]

    CredencialWebAuthn.objects.create(
        usuario=request.user,
        credential_id=cred_id_b64,
        public_key=bytes_to_base64url(verificacion.credential_public_key),
        sign_count=verificacion.sign_count,
        transports=transportes[:255],
        nombre_dispositivo=nombre,
        ultimo_uso=timezone.now(),
    )
    return JsonResponse({'ok': True})


# ── Login biométrico ─────────────────────────────────────────────────────────

@require_POST
def opciones_login(request):
    try:
        webauthn = _wa()
    except RuntimeError as e:
        return _error(str(e), status=503)
    from webauthn.helpers import bytes_to_base64url
    from webauthn.helpers.structs import UserVerificationRequirement

    # Login sin nombre de usuario (passkey descubrible). El autenticador elige
    # una credencial y el servidor identifica al usuario por su ID.
    opciones = webauthn.generate_authentication_options(
        rp_id=_rp_id(),
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    request.session['webauthn_auth_challenge'] = bytes_to_base64url(opciones.challenge)
    return HttpResponse(webauthn.options_to_json(opciones), content_type='application/json')


@require_POST
def verificar_login(request):
    try:
        webauthn = _wa()
    except RuntimeError as e:
        return _error(str(e), status=503)
    from webauthn.helpers import base64url_to_bytes

    reto = request.session.pop('webauthn_auth_challenge', None)
    if not reto:
        return _error("No hay un inicio de sesión en curso. Inténtalo de nuevo.")
    try:
        cuerpo = request.body.decode('utf-8')
        datos = json.loads(cuerpo)
    except (ValueError, UnicodeDecodeError):
        return _error("Datos inválidos.")

    cred_id = datos.get('id') or datos.get('rawId')
    if not cred_id:
        return _error("Respuesta incompleta.")

    credencial = (
        CredencialWebAuthn.objects.select_related('usuario')
        .filter(credential_id=cred_id).first()
    )
    if credencial is None:
        return _error("Este dispositivo no está registrado. Inicia sesión con tu contraseña.")

    try:
        verificacion = webauthn.verify_authentication_response(
            credential=cuerpo,
            expected_challenge=base64url_to_bytes(reto),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=base64url_to_bytes(credencial.public_key),
            credential_current_sign_count=credencial.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        logger.warning("WebAuthn login fallido (cred %s): %s", credencial.pk, exc)
        return _error("No se pudo verificar la huella. Inténtalo de nuevo.")

    usuario = credencial.usuario
    if not usuario.is_active:
        return _error("Tu cuenta está inactiva. Contacta a tu institución.")
    institucion = getattr(usuario, 'institucion_asociada', None)
    if institucion is not None and not getattr(institucion, 'activa', True):
        return _error("El acceso de tu institución está suspendido.")

    # Actualiza contador anti-clonación y marca último uso.
    credencial.sign_count = verificacion.new_sign_count
    credencial.ultimo_uso = timezone.now()
    credencial.save(update_fields=['sign_count', 'ultimo_uso'])

    # Inicia sesión (sin authenticate(): fijamos backend explícito).
    usuario.backend = 'django.contrib.auth.backends.ModelBackend'
    auth_login(request, usuario)
    return JsonResponse({'ok': True, 'redirect': '/'})


@require_POST
@login_required
def eliminar(request, pk):
    cred = CredencialWebAuthn.objects.filter(pk=pk, usuario=request.user).first()
    if cred:
        cred.delete()
        messages.success(request, "Dispositivo eliminado.")
    return redirect('passkeys:gestionar')
