"""Pruebas mínimas de acceso académico y mora (helpers compartidos)."""

from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from gestion_academica.decorators import redirect_si_moroso_estudiante, estudiante_esta_al_dia
from gestion_academica.utils import docente_asignado_a_actividad


class RedirectMorosoTests(SimpleTestCase):
    def test_anonimo_no_redirige(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.user = AnonymousUser()
        self.assertIsNone(redirect_si_moroso_estudiante(req))


class DocenteAsignadoTests(SimpleTestCase):
    def test_usuario_sin_atributo_docente_false(self):
        user = object()
        act = MagicMock()
        act.curso.docentes_asignados.filter.return_value.exists.return_value = True
        self.assertFalse(docente_asignado_a_actividad(user, act))

    def test_docente_en_curso_true(self):
        user = MagicMock()
        user.docente = MagicMock(pk=7)
        act = MagicMock()
        act.curso.docentes_asignados.filter.return_value.exists.return_value = True
        self.assertTrue(docente_asignado_a_actividad(user, act))


class EstudianteEstaAlDiaSmokeTest(SimpleTestCase):
    """Solo verifica que el helper no revienta con usuario anónimo."""

    def test_anonimo_true_none(self):
        rf = RequestFactory()
        req = rf.get("/")
        req.user = AnonymousUser()
        al_dia, est = estudiante_esta_al_dia(req)
        self.assertTrue(al_dia)
        self.assertIsNone(est)
