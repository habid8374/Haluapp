from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, get_connection
from django.conf import settings
from django.urls import reverse
from .models import InscripcionCurso

@receiver(post_save, sender=InscripcionCurso)
def notificar_inscripcion_curso(sender, instance, created, **kwargs):
    """
    Envía un correo al estudiante con el enlace al curso cuando es matriculado (inscripción creada y activa).
    """
    if created and instance.activo:
        estudiante = instance.estudiante
        curso = instance.curso
        institucion = curso.institucion
        
        # Intentamos obtener el email del usuario asociado al estudiante
        email_destino = None
        if estudiante.usuario and estudiante.usuario.email:
            email_destino = estudiante.usuario.email
        
        if email_destino:
            # Construir URL del curso. 
            # Nota: En producción, request.build_absolute_uri es mejor, pero en señales no tenemos request.
            # Se recomienda definir una variable DOMINIO_BASE en settings.py.
            # Por ahora usaremos una ruta relativa o un dominio hardcodeado si es necesario.
            try:
                path = reverse('cursos:aula_virtual', args=[curso.id])
                # Ajusta este dominio según tu entorno (localhost o producción)
                dominio = getattr(settings, 'DOMINIO_BASE', 'http://127.0.0.1:8000') 
                url_curso = f"{dominio}{path}"
            except Exception:
                url_curso = "#"

            asunto = f"Bienvenido al curso: {curso.nombre}"
            mensaje = f"""
            Hola {estudiante.usuario.first_name},
            
            Has sido matriculado exitosamente en el curso "{curso.nombre}".
            
            Puedes acceder al contenido y comenzar tus clases ingresando al siguiente enlace:
            {url_curso}
            
            ¡Muchos éxitos!
            """
            
            # Configuración dinámica del servidor SMTP
            connection = None
            from_email = settings.DEFAULT_FROM_EMAIL
            
            if institucion.email_host_user and institucion.email_host_password:
                connection = get_connection(
                    host=institucion.email_host or 'smtp.gmail.com', # Default a Gmail si no está definido
                    port=institucion.email_port or 587,
                    username=institucion.email_host_user,
                    password=institucion.email_host_password,
                    use_tls=institucion.email_use_tls
                )
                from_email = institucion.email_host_user
            
            try:
                send_mail(
                    asunto,
                    mensaje,
                    from_email,
                    [email_destino],
                    connection=connection,
                    fail_silently=True
                )
            except Exception as e:
                print(f"Error enviando correo curso: {e}")
