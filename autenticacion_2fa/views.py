from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import DispositivoTOTP


@login_required
def configurar_2fa(request):
    """Muestra el QR para configurar el autenticador y confirma el dispositivo."""
    usuario = request.user
    disp = DispositivoTOTP.crear_para(usuario)

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().replace(' ', '')
        if disp.verificar(codigo):
            disp.confirmado = True
            disp.save()
            messages.success(request, 'Autenticación de dos factores activada correctamente.')
            return redirect(reverse('gestion_academica:inicio_academico'))
        else:
            messages.error(request, 'Código incorrecto. Verifica tu aplicación autenticadora.')

    return render(request, 'autenticacion_2fa/configurar.html', {
        'qr_base64': disp.qr_base64(),
        'ya_confirmado': disp.confirmado,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def verificar_2fa(request):
    """Solicita el código TOTP en cada inicio de sesión."""
    next_url = request.GET.get('next') or request.POST.get('next') or reverse('gestion_academica:inicio_academico')

    # Si ya verificó en esta sesión, continuar
    if request.session.get('2fa_verificado', False):
        return redirect(next_url)

    try:
        disp = request.user.dispositivo_totp
    except Exception:
        return redirect(next_url)

    if not disp.confirmado:
        return redirect(reverse('2fa:configurar'))

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip().replace(' ', '')
        if disp.verificar(codigo):
            request.session['2fa_verificado'] = True
            return redirect(next_url)
        else:
            messages.error(request, 'Código incorrecto. Intenta de nuevo.')

    return render(request, 'autenticacion_2fa/verificar.html', {'next': next_url})


@login_required
def desactivar_2fa(request):
    """Desactiva el 2FA del usuario (requiere confirmación)."""
    if request.method == 'POST':
        try:
            request.user.dispositivo_totp.delete()
            request.session.pop('2fa_verificado', None)
            messages.success(request, 'Autenticación de dos factores desactivada.')
        except Exception:
            pass
        return redirect(reverse('2fa:configurar'))

    return render(request, 'autenticacion_2fa/desactivar_confirm.html')
