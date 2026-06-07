from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def google_socialapp_configured(context):
    """
    True solo si django-allauth puede resolver la app de Google para esta petición
    (misma lógica que {% provider_login_url 'google' %}).
    Un .exists() en ORM no basta: get_app puede seguir lanzando DoesNotExist.
    """
    request = context.get("request")
    if request is None:
        return False
    try:
        from allauth.socialaccount.adapter import get_adapter
        from allauth.socialaccount.models import SocialApp
    except Exception:
        return False
    try:
        get_adapter().get_app(request, provider="google")
        return True
    except SocialApp.DoesNotExist:
        return False
    except Exception:
        # p. ej. MultipleObjectsReturned si hay varias apps visibles
        return False
