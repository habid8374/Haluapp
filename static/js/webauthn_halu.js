/*
 * WebAuthn (Passkeys) para Halu — registro de dispositivo e inicio de sesión
 * biométrico. Vanilla JS, sin dependencias.
 */
(function (global) {
  'use strict';

  function b64urlToBuf(s) {
    const pad = '='.repeat((4 - (s.length % 4)) % 4);
    const b64 = (s + pad).replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes.buffer;
  }

  function bufToB64url(buf) {
    const bytes = new Uint8Array(buf);
    let bin = '';
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }

  async function postJSON(url, csrf, body) {
    const headers = { 'X-CSRFToken': csrf };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const resp = await fetch(url, {
      method: 'POST',
      headers: headers,
      credentials: 'same-origin',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let datos = null;
    try { datos = await resp.json(); } catch (e) { datos = null; }
    if (!resp.ok) {
      const msg = (datos && datos.error) ? datos.error : 'Error del servidor (' + resp.status + ')';
      throw new Error(msg);
    }
    return datos;
  }

  // ¿El dispositivo tiene autenticador biométrico de plataforma?
  async function soportado() {
    if (!global.PublicKeyCredential ||
        !global.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable) {
      return false;
    }
    try {
      return await global.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
    } catch (e) {
      return false;
    }
  }

  // Registro de este dispositivo (usuario ya autenticado).
  async function registrar(opcionesUrl, verificarUrl, csrf, nombreDispositivo) {
    // 1) Pedir opciones (challenge) al servidor.
    const resp = await fetch(opcionesUrl, {
      method: 'POST', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin',
    });
    if (!resp.ok) {
      let d = null; try { d = await resp.json(); } catch (e) {}
      throw new Error((d && d.error) || 'No se pudieron obtener las opciones.');
    }
    const opciones = await resp.json();

    // 2) Convertir base64url -> ArrayBuffer.
    opciones.challenge = b64urlToBuf(opciones.challenge);
    opciones.user.id = b64urlToBuf(opciones.user.id);
    if (opciones.excludeCredentials) {
      opciones.excludeCredentials.forEach(function (c) { c.id = b64urlToBuf(c.id); });
    }

    // 3) Crear la credencial con el autenticador (huella/rostro).
    const cred = await navigator.credentials.create({ publicKey: opciones });

    // 4) Serializar la respuesta y enviarla al servidor.
    const cuerpo = {
      id: cred.id,
      rawId: bufToB64url(cred.rawId),
      type: cred.type,
      authenticatorAttachment: cred.authenticatorAttachment || null,
      clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
      response: {
        clientDataJSON: bufToB64url(cred.response.clientDataJSON),
        attestationObject: bufToB64url(cred.response.attestationObject),
        transports: cred.response.getTransports ? cred.response.getTransports() : [],
      },
      nombre_dispositivo: nombreDispositivo || 'Mi dispositivo',
    };
    return await postJSON(verificarUrl, csrf, cuerpo);
  }

  // Login biométrico (usuario anónimo).
  async function login(opcionesUrl, verificarUrl, csrf) {
    const resp = await fetch(opcionesUrl, {
      method: 'POST', headers: { 'X-CSRFToken': csrf }, credentials: 'same-origin',
    });
    if (!resp.ok) {
      let d = null; try { d = await resp.json(); } catch (e) {}
      throw new Error((d && d.error) || 'No se pudieron obtener las opciones.');
    }
    const opciones = await resp.json();

    opciones.challenge = b64urlToBuf(opciones.challenge);
    if (opciones.allowCredentials) {
      opciones.allowCredentials.forEach(function (c) { c.id = b64urlToBuf(c.id); });
    }

    const assertion = await navigator.credentials.get({ publicKey: opciones });

    const cuerpo = {
      id: assertion.id,
      rawId: bufToB64url(assertion.rawId),
      type: assertion.type,
      authenticatorAttachment: assertion.authenticatorAttachment || null,
      clientExtensionResults: assertion.getClientExtensionResults ? assertion.getClientExtensionResults() : {},
      response: {
        clientDataJSON: bufToB64url(assertion.response.clientDataJSON),
        authenticatorData: bufToB64url(assertion.response.authenticatorData),
        signature: bufToB64url(assertion.response.signature),
        userHandle: assertion.response.userHandle ? bufToB64url(assertion.response.userHandle) : null,
      },
    };
    return await postJSON(verificarUrl, csrf, cuerpo);
  }

  // Traduce errores comunes del navegador a mensajes amigables.
  function mensajeError(err) {
    if (!err) return 'Ocurrió un error.';
    if (err.name === 'NotAllowedError') return 'Se canceló o no se detectó la huella. Inténtalo de nuevo.';
    if (err.name === 'InvalidStateError') return 'Este dispositivo ya estaba registrado.';
    if (err.name === 'SecurityError') return 'Problema de seguridad del dominio. Verifica que estás en el sitio oficial (https).';
    if (err.name === 'AbortError') return 'La operación se canceló.';
    return err.message || 'Ocurrió un error.';
  }

  global.HaluPasskeys = {
    soportado: soportado,
    registrar: registrar,
    login: login,
    mensajeError: mensajeError,
  };
})(window);
