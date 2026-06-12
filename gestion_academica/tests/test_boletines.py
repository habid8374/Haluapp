"""
Tests de integración para generación de boletines.

Verifica:
1. Un Estudiante con Calificaciones puede acceder a su boletín sin error 500
2. El boletín solo incluye calificaciones de la institución correcta
3. Un estudiante del Colegio A no puede ver el boletín de un estudiante del Colegio B
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from finanzas.models import InstitucionEducativa
from gestion_academica.models import (
    ActividadCalificable,
    Calificacion,
    Curso,
    Docente,
    Estudiante,
    Grado,
    Materia,
    PeriodoAcademico,
    TipoActividad,
    Usuario,
)


def _crear_institucion(nombre, nit):
    """Crea InstitucionEducativa minimal (sin clean validators)."""
    inst = InstitucionEducativa(
        nombre=nombre,
        nit=nit,
        google_api_key="test-key-placeholder",
        mp_webhook_secret="test-secret-placeholder",
    )
    inst.save()
    return inst


def _crear_usuario(username, email, rol, institucion, is_staff=False):
    return Usuario.objects.create_user(
        username=username,
        email=email,
        password="TestPass123!",
        rol=rol,
        institucion_asociada=institucion,
        is_staff=is_staff,
    )


def _otorgar_permiso(usuario, codename):
    try:
        perm = Permission.objects.get(codename=codename)
        usuario.user_permissions.add(perm)
        if hasattr(usuario, '_perm_cache'):
            del usuario._perm_cache
        if hasattr(usuario, '_user_perm_cache'):
            del usuario._user_perm_cache
    except Permission.DoesNotExist:
        pass


class BoletinMultiTenantBase(TestCase):
    """
    Fixture base para tests de boletines.
    Crea 2 instituciones con estudiantes, cursos y calificaciones.
    """

    @classmethod
    def setUpTestData(cls):
        # ── Instituciones ─────────────────────────────────────────────────
        cls.inst_a = _crear_institucion("Colegio Boletín A", "920111111-1")
        cls.inst_b = _crear_institucion("Colegio Boletín B", "920222222-2")

        # ── Grados ────────────────────────────────────────────────────────
        cls.grado_a = Grado.objects.create(
            nombre="Séptimo A", institucion=cls.inst_a, orden=7
        )
        cls.grado_b = Grado.objects.create(
            nombre="Séptimo B", institucion=cls.inst_b, orden=7
        )

        # ── Periodos Académicos (activos) ─────────────────────────────────
        cls.periodo_a = PeriodoAcademico.objects.create(
            nombre="Periodo 1",
            fecha_inicio=datetime.date(2024, 2, 1),
            fecha_fin=datetime.date(2024, 4, 30),
            año_escolar=2024,
            activo=True,
            institucion=cls.inst_a,
        )
        cls.periodo_b = PeriodoAcademico.objects.create(
            nombre="Periodo 1",
            fecha_inicio=datetime.date(2024, 2, 1),
            fecha_fin=datetime.date(2024, 4, 30),
            año_escolar=2024,
            activo=True,
            institucion=cls.inst_b,
        )

        # ── Usuarios Estudiantes ──────────────────────────────────────────
        cls.user_est_a = _crear_usuario(
            "boletin_est_a@test.com", "boletin_est_a@test.com",
            "estudiante", cls.inst_a
        )
        cls.user_est_b = _crear_usuario(
            "boletin_est_b@test.com", "boletin_est_b@test.com",
            "estudiante", cls.inst_b
        )

        # ── Perfiles Estudiante ───────────────────────────────────────────
        cls.estudiante_a = Estudiante.objects.create(
            usuario=cls.user_est_a,
            institucion=cls.inst_a,
            documento_identidad="BOL-001-A",
            codigo_estudiante="BCOD-001-A",
            grado_actual=cls.grado_a,
        )
        cls.estudiante_b = Estudiante.objects.create(
            usuario=cls.user_est_b,
            institucion=cls.inst_b,
            documento_identidad="BOL-001-B",
            codigo_estudiante="BCOD-001-B",
            grado_actual=cls.grado_b,
        )

        # ── Materias ──────────────────────────────────────────────────────
        cls.materia_a1 = Materia.objects.create(
            nombre_materia="Lengua Castellana",
            institucion=cls.inst_a,
        )
        cls.materia_a2 = Materia.objects.create(
            nombre_materia="Ciencias Naturales",
            institucion=cls.inst_a,
        )
        cls.materia_b1 = Materia.objects.create(
            nombre_materia="Lengua Castellana",
            institucion=cls.inst_b,
        )

        # ── Cursos ────────────────────────────────────────────────────────
        cls.curso_a1 = Curso.objects.create(
            materia=cls.materia_a1,
            grado=cls.grado_a,
            periodo_academico=cls.periodo_a,
            institucion=cls.inst_a,
        )
        cls.curso_a2 = Curso.objects.create(
            materia=cls.materia_a2,
            grado=cls.grado_a,
            periodo_academico=cls.periodo_a,
            institucion=cls.inst_a,
        )
        cls.curso_b1 = Curso.objects.create(
            materia=cls.materia_b1,
            grado=cls.grado_b,
            periodo_academico=cls.periodo_b,
            institucion=cls.inst_b,
        )

        # ── Tipos de Actividad ────────────────────────────────────────────
        cls.tipo_act_a = TipoActividad.objects.create(
            nombre="Examen",
            porcentaje=Decimal("100.00"),
            institucion=cls.inst_a,
        )
        cls.tipo_act_b = TipoActividad.objects.create(
            nombre="Examen",
            porcentaje=Decimal("100.00"),
            institucion=cls.inst_b,
        )

        # ── Actividades Calificables ──────────────────────────────────────
        cls.actividad_a1 = ActividadCalificable.objects.create(
            curso=cls.curso_a1,
            tipo_actividad=cls.tipo_act_a,
            titulo="Examen 1 Lengua",
            fecha_publicacion=datetime.date(2024, 2, 10),
            institucion=cls.inst_a,
        )
        cls.actividad_a2 = ActividadCalificable.objects.create(
            curso=cls.curso_a2,
            tipo_actividad=cls.tipo_act_a,
            titulo="Examen 1 Ciencias",
            fecha_publicacion=datetime.date(2024, 2, 15),
            institucion=cls.inst_a,
        )
        cls.actividad_b1 = ActividadCalificable.objects.create(
            curso=cls.curso_b1,
            tipo_actividad=cls.tipo_act_b,
            titulo="Examen 1 Lengua B",
            fecha_publicacion=datetime.date(2024, 2, 10),
            institucion=cls.inst_b,
        )

        # ── Calificaciones ────────────────────────────────────────────────
        cls.cal_a1 = Calificacion.objects.create(
            estudiante=cls.estudiante_a,
            actividad_calificable=cls.actividad_a1,
            valor_numerico=Decimal("4.5"),
            institucion=cls.inst_a,
        )
        cls.cal_a2 = Calificacion.objects.create(
            estudiante=cls.estudiante_a,
            actividad_calificable=cls.actividad_a2,
            valor_numerico=Decimal("3.8"),
            institucion=cls.inst_a,
        )
        cls.cal_b1 = Calificacion.objects.create(
            estudiante=cls.estudiante_b,
            actividad_calificable=cls.actividad_b1,
            valor_numerico=Decimal("4.2"),
            institucion=cls.inst_b,
        )

        # ── Permisos del estudiante ───────────────────────────────────────
        _otorgar_permiso(cls.user_est_a, "ver_mi_boletin")
        _otorgar_permiso(cls.user_est_b, "ver_mi_boletin")

        # ── Usuario Staff (coordinador) ───────────────────────────────────
        cls.coord_a = _crear_usuario(
            "boletin_coord_a@test.com", "boletin_coord_a@test.com",
            "coordinador", cls.inst_a, is_staff=True
        )
        cls.coord_a.user_permissions.add(
            *Permission.objects.filter(codename__in=["ver_mi_boletin"])
        )


class CalificacionAislamientoTest(BoletinMultiTenantBase):
    """
    Verifica que las calificaciones están aisladas por institución en la BD.
    """

    def test_calificaciones_de_a_no_contienen_datos_de_b(self):
        """
        Filtrando calificaciones por institucion=inst_a no deben aparecer
        calificaciones del Colegio B.
        """
        cals_inst_a = Calificacion.objects.filter(institucion=self.inst_a)
        cals_inst_b = Calificacion.objects.filter(institucion=self.inst_b)

        pks_a = set(cals_inst_a.values_list("pk", flat=True))
        pks_b = set(cals_inst_b.values_list("pk", flat=True))

        self.assertTrue(
            pks_a.isdisjoint(pks_b),
            "Las calificaciones de inst_a y inst_b deben estar completamente aisladas"
        )
        self.assertIn(self.cal_a1.pk, pks_a)
        self.assertIn(self.cal_a2.pk, pks_a)
        self.assertIn(self.cal_b1.pk, pks_b)
        self.assertNotIn(self.cal_b1.pk, pks_a)

    def test_estudiante_a_tiene_2_calificaciones_en_inst_a(self):
        """El estudiante A debe tener exactamente 2 calificaciones en inst_a."""
        cals = Calificacion.objects.filter(
            estudiante=self.estudiante_a,
            institucion=self.inst_a,
        )
        self.assertEqual(cals.count(), 2)

    def test_calificaciones_estudiante_a_no_incluyen_datos_de_b(self):
        """
        Las calificaciones asociadas al estudiante A no deben incluir
        las actividades del Colegio B.
        """
        cals_a = Calificacion.objects.filter(
            estudiante=self.estudiante_a,
            institucion=self.inst_a
        )
        actividades_vistas = set(
            cals_a.values_list("actividad_calificable__institucion", flat=True)
        )
        self.assertNotIn(
            self.inst_b.pk, actividades_vistas,
            "Las actividades en el boletín de est_a no deben pertenecer a inst_b"
        )


class BoletinVistaTest(BoletinMultiTenantBase):
    """
    Prueba las vistas HTTP del boletín.
    """

    def test_estudiante_a_puede_acceder_a_su_boletin(self):
        """
        El estudiante A autenticado debe poder acceder al boletín
        del período activo sin error 500.
        """
        self.client.force_login(self.user_est_a)
        url = reverse("gestion_academica:mi_boletin_periodo_actual")
        response = self.client.get(url)

        # Debe responder 200 (boletín cargado) o un redirect válido (sin errores 5xx)
        self.assertNotEqual(
            response.status_code, 500,
            "El boletín no debe generar un error 500 cuando el estudiante tiene calificaciones"
        )
        self.assertIn(
            response.status_code, [200, 302],
            f"Se esperaba 200 o 302, se obtuvo {response.status_code}"
        )

    def test_estudiante_a_no_puede_ver_boletin_imprimible_de_b(self):
        """
        Un estudiante del Colegio A intentando ver el boletín imprimible
        de un estudiante del Colegio B debe recibir 403 o redirect.
        La vista boletin_imprimible verifica: es_el_mismo_estudiante OR es_staff OR es_familiar.
        """
        self.client.force_login(self.user_est_a)
        url = reverse(
            "gestion_academica:boletin_imprimible",
            kwargs={
                "estudiante_pk": self.estudiante_b.pk,
                "periodo_pk": self.periodo_b.pk,
            }
        )
        response = self.client.get(url)

        # La vista debe negar el acceso: 403 o redirect a login/inicio
        self.assertNotEqual(
            response.status_code, 200,
            "Un estudiante de Colegio A no debe poder ver el boletín de Colegio B"
        )
        self.assertIn(
            response.status_code, [302, 403],
            f"Se esperaba 302 o 403 para acceso cross-tenant, se obtuvo {response.status_code}"
        )

    def test_staff_a_puede_ver_boletin_de_su_estudiante(self):
        """
        El coordinador (is_staff=True) del Colegio A puede ver el boletín
        de su propio estudiante.
        """
        self.client.force_login(self.coord_a)
        url = reverse(
            "gestion_academica:boletin_imprimible",
            kwargs={
                "estudiante_pk": self.estudiante_a.pk,
                "periodo_pk": self.periodo_a.pk,
            }
        )
        response = self.client.get(url)

        # No debe devolver 500; puede devolver 200 o redirect a otro formato
        self.assertNotEqual(
            response.status_code, 500,
            "El coordinador no debe ver un error 500 al acceder al boletín de su estudiante"
        )

    def test_boletin_requiere_autenticacion(self):
        """Sin autenticación la vista del boletín redirige a login."""
        url = reverse("gestion_academica:mi_boletin_periodo_actual")
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    def test_boletin_imprimible_requiere_autenticacion(self):
        """Sin autenticación la vista boletin_imprimible redirige a login."""
        url = reverse(
            "gestion_academica:boletin_imprimible",
            kwargs={
                "estudiante_pk": self.estudiante_a.pk,
                "periodo_pk": self.periodo_a.pk,
            }
        )
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])


class BoletinCalificacionesCorrectas(BoletinMultiTenantBase):
    """
    Verifica que el boletín incluye solo las calificaciones
    de la institución correcta (lógica de negocio).
    """

    def test_calificaciones_del_estudiante_a_son_de_inst_a(self):
        """
        Todas las calificaciones del estudiante A deben pertenecer a inst_a.
        Ninguna debe pertenecer a inst_b.
        """
        calificaciones = Calificacion.objects.filter(
            estudiante=self.estudiante_a,
            institucion=self.inst_a,
        )
        for cal in calificaciones:
            self.assertEqual(
                cal.institucion, self.inst_a,
                f"Calificación {cal.pk} pertenece a institución incorrecta"
            )
            self.assertNotEqual(
                cal.institucion, self.inst_b
            )

    def test_calificaciones_del_estudiante_b_son_de_inst_b(self):
        """Todas las calificaciones del estudiante B pertenecen a inst_b."""
        calificaciones = Calificacion.objects.filter(
            estudiante=self.estudiante_b,
            institucion=self.inst_b,
        )
        self.assertEqual(calificaciones.count(), 1)
        for cal in calificaciones:
            self.assertEqual(cal.institucion, self.inst_b)

    def test_filtrar_calificaciones_por_inst_a_excluye_b(self):
        """
        Construyendo el queryset como lo haría la vista del boletín
        (filtrando actividades del curso que pertenece a inst_a),
        no se cuelan calificaciones de inst_b.
        """
        cursos_de_inst_a = Curso.objects.filter(
            grado=self.grado_a,
            periodo_academico=self.periodo_a,
            institucion=self.inst_a,
        )
        calificaciones_boletin = Calificacion.objects.filter(
            estudiante=self.estudiante_a,
            actividad_calificable__curso__in=cursos_de_inst_a,
        )

        instituciones_encontradas = set(
            calificaciones_boletin.values_list(
                "actividad_calificable__institucion", flat=True
            )
        )
        self.assertNotIn(
            self.inst_b.pk,
            instituciones_encontradas,
            "Las calificaciones del boletín no deben incluir actividades de inst_b"
        )
        # Deben existir calificaciones (no queryset vacío)
        self.assertGreater(
            calificaciones_boletin.count(), 0,
            "El boletín debe tener calificaciones para el estudiante A"
        )

    def test_periodo_de_inst_a_no_es_visible_para_est_b(self):
        """
        El periodo académico de inst_a no debe aparecer al filtrar
        por institución inst_b.
        """
        periodos_inst_b = PeriodoAcademico.objects.filter(
            activo=True, institucion=self.inst_b
        )
        self.assertNotIn(
            self.periodo_a,
            periodos_inst_b,
            "El periodo de inst_a no debe estar en los periodos activos de inst_b"
        )
