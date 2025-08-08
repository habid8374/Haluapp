# finanzas/mixins.py

import logging

# Definir el logger para este módulo
logger = logging.getLogger(__name__)

class InstitucionOwnedMixin:
    """
    Mixin para Clases Basadas en Vistas que filtra el queryset para que un usuario
    solo vea los objetos pertenecientes a su institución.
    Los superusuarios pueden ver todo.
    """
    def get_queryset(self):
        # Obtiene el queryset original definido en la vista
        queryset = super().get_queryset()
        
        
        if not self.request.user.is_superuser:
            institucion_usuario = getattr(self.request.user, 'institucion_asociada', None)
            if institucion_usuario:
                return queryset.filter(institucion=institucion_usuario)
            else:
                logger.warning(f"Usuario sin institución: {self.request.user.username}")
                return queryset.none()
        return queryset