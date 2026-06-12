"""
Tests de integración para flujos de finanzas multi-institución.

Verifica:
1. Que CuentaPorCobrarEstudiante se asigna a la institución correcta
2. Que un usuario de finanzas del Colegio A no puede ver cuentas del Colegio B
3. Que PagoRegistrado queda asociado a la institución correcta
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from finanzas.models import (
    CuentaPorCobrarEstudiante,
    ConceptoPago,
    InstitucionEducativa,
    PagoRegistrado,
    TipoConceptoPago,
)
from gestion_academica.models import (
    Estudiante,
    Grado,
    Materia,
    PeriodoAcademico,
    Usuario,
)


def _crear_institucion(nombre, nit):
    """Crea una InstitucionEducativa minimal válida (omite validadores de clean)."""
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


class FinanzasMultiTenantBase(TestCase):
    """
    Base con fixtures compartidos para los tests de finanzas.
    Crea 2 instituciones con todos sus modelos relacionados.
    """

    @classmethod
    def setUpTestData(cls):
        # ── Instituciones ─────────────────────────────────────────────────
        cls.inst_a = _crear_institucion("Colegio Finanzas A", "910111111-1")
        cls.inst_b = _crear_institucion("Colegio Finanzas B", "910222222-2")

        # ── Usuarios de finanzas ──────────────────────────────────────────
        cls.admin_a = _crear_usuario(
            "admin_fin_a@test.com", "admin_fin_a@test.com",
            "administrador", cls.inst_a, is_staff=True
        )
        cls.admin_b = _crear_usuario(
            "admin_fin_b@test.com", "admin_fin_b@test.com",
            "administrador", cls.inst_b, is_staff=True
        )

        # ── Grados ────────────────────────────────────────────────────────
        cls.grado_a = Grado.objects.create(
            nombre="Sexto A", institucion=cls.inst_a, orden=6
        )
        cls.grado_b = Grado.objects.create(
            nombre="Sexto B", institucion=cls.inst_b, orden=6
        )

        # ── Estudiantes ───────────────────────────────────────────────────
        cls.user_est_a = _crear_usuario(
            "est_fin_a@test.com", "est_fin_a@test.com",
            "estudiante", cls.inst_a
        )
        cls.user_est_b = _crear_usuario(
            "est_fin_b@test.com", "est_fin_b@test.com",
            "estudiante", cls.inst_b
        )
        cls.estudiante_a = Estudiante.objects.create(
            usuario=cls.user_est_a,
            institucion=cls.inst_a,
            documento_identidad="FIN-001-A",
            codigo_estudiante="FCOD-001-A",
            grado_actual=cls.grado_a,
        )
        cls.estudiante_b = Estudiante.objects.create(
            usuario=cls.user_est_b,
            institucion=cls.inst_b,
            documento_identidad="FIN-001-B",
            codigo_estudiante="FCOD-001-B",
            grado_actual=cls.grado_b,
        )

        # ── Tipos de Concepto de Pago ─────────────────────────────────────
        cls.tipo_concepto_a = TipoConceptoPago.objects.create(
            nombre="Mensualidad",
            institucion=cls.inst_a,
        )
        cls.tipo_concepto_b = TipoConceptoPago.objects.create(
            nombre="Mensualidad",
            institucion=cls.inst_b,
        )

        # ── Conceptos de Pago ─────────────────────────────────────────────
        cls.concepto_a = ConceptoPago.objects.create(
            tipo_concepto=cls.tipo_concepto_a,
            nombre_concepto="Pensión Febrero",
            valor=Decimal("500000.00"),
            fecha_vencimiento_general=datetime.date(2024, 2, 28),
            institucion=cls.inst_a,
        )
        cls.concepto_b = ConceptoPago.objects.create(
            tipo_concepto=cls.tipo_concepto_b,
            nombre_concepto="Pensión Febrero",
            valor=Decimal("400000.00"),
            fecha_vencimiento_general=datetime.date(2024, 2, 28),
            institucion=cls.inst_b,
        )

        # ── Otorgar permisos de finanzas ──────────────────────────────────
        for codename in (
            "view_cuentaporcobrarestudiante",
            "add_cuentaporcobrarestudiante",
            "change_cuentaporcobrarestudiante",
            "add_pagoregistrado",
            "view_pagoregistrado",
            "acceso_modulo_finanzas",
        ):
            _otorgar_permiso(cls.admin_a, codename)
            _otorgar_permiso(cls.admin_b, codename)


class CuentaPorCobrarInstitucionTest(FinanzasMultiTenantBase):
    """Prueba que CuentaPorCobrarEstudiante se asigna correctamente a la institución."""

    def test_cuenta_hereda_institucion_del_estudiante(self):
        """
        Al crear una CuentaPorCobrarEstudiante con un estudiante,
        la institución debe heredarse automáticamente del estudiante.
        """
        cuenta = CuentaPorCobrarEstudiante.objects.create(
            estudiante=self.estudiante_a,
            concepto_pago=self.concepto_a,
            monto_asignado=Decimal("500000.00"),
            fecha_vencimiento_especifica=datetime.date(2024, 2, 28),
        )
        self.assertEqual(
            cuenta.institucion, self.inst_a,
            "La cuenta debe heredar la institución del estudiante automáticamente"
        )

    def test_cuenta_de_b_tiene_institucion_b(self):
        """La cuenta del estudiante B debe quedar con la institución B."""
        cuenta = CuentaPorCobrarEstudiante.objects.create(
            estudiante=self.estudiante_b,
            concepto_pago=self.concepto_b,
            monto_asignado=Decimal("400000.00"),
            fecha_vencimiento_especifica=datetime.date(2024, 2, 28),
        )
        self.assertEqual(cuenta.institucion, self.inst_b)

    def test_estado_inicial_es_pendiente(self):
        """Una cuenta recién creada sin pagos debe estar en estado PENDIENTE."""
        cuenta = CuentaPorCobrarEstudiante.objects.create(
            estudiante=self.estudiante_a,
            concepto_pago=self.concepto_a,
            monto_asignado=Decimal("500000.00"),
            fecha_vencimiento_especifica=datetime.date(2099, 12, 31),
        )
        self.assertIn(
            cuenta.estado, ["PENDIENTE", "VENCIDO"],
            "Una cuenta nueva sin pagos debe ser PENDIENTE o VENCIDO según la fecha"
        )


class CuentaVisibilidadCrossTenanTest(FinanzasMultiTenantBase):
    """Prueba que usuario del Colegio A no puede ver cuentas del Colegio B."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Crear cuentas en ambas instituciones
        cls.cuenta_a = CuentaPorCobrarEstudiante.objects.create(
            estudiante=cls.estudiante_a,
            concepto_pago=cls.concepto_a,
            monto_asignado=Decimal("500000.00"),
            fecha_vencimiento_especifica=datetime.date(2099, 12, 31),
        )
        cls.cuenta_b = CuentaPorCobrarEstudiante.objects.create(
            estudiante=cls.estudiante_b,
            concepto_pago=cls.concepto_b,
            monto_asignado=Decimal("400000.00"),
            fecha_vencimiento_especifica=datetime.date(2099, 12, 31),
        )

    def test_filtro_por_institucion_en_bd(self):
        """
        El queryset filtrado por institución A no debe incluir cuentas de institución B.
        """
        cuentas_inst_a = CuentaPorCobrarEstudiante.objects.filter(
            institucion=self.inst_a
        )
        cuentas_inst_b = CuentaPorCobrarEstudiante.objects.filter(
            institucion=self.inst_b
        )

        pks_a = set(cuentas_inst_a.values_list("pk", flat=True))
        pks_b = set(cuentas_inst_b.values_list("pk", flat=True))

        self.assertTrue(
            pks_a.isdisjoint(pks_b),
            "Las cuentas por cobrar deben estar aisladas por institución"
        )
        self.assertIn(self.cuenta_a.pk, pks_a)
        self.assertIn(self.cuenta_b.pk, pks_b)

    def test_admin_a_no_ve_cuentas_de_b_en_bd(self):
        """
        Simulando la lógica de la vista: admin_a solo ve cuentas de inst_a.
        """
        cuentas_visibles = CuentaPorCobrarEstudiante.objects.filter(
            institucion=self.admin_a.institucion_asociada
        )
        self.assertIn(self.cuenta_a, cuentas_visibles)
        self.assertNotIn(self.cuenta_b, cuentas_visibles)

    def test_admin_b_no_ve_cuentas_de_a_en_bd(self):
        """Admin B solo ve las cuentas de su institución."""
        cuentas_visibles = CuentaPorCobrarEstudiante.objects.filter(
            institucion=self.admin_b.institucion_asociada
        )
        self.assertIn(self.cuenta_b, cuentas_visibles)
        self.assertNotIn(self.cuenta_a, cuentas_visibles)

    def test_historial_cuentas_requiere_autenticacion(self):
        """La vista de historial de cuentas requiere autenticación."""
        url = reverse(
            "finanzas:historial_cuentas_estudiante",
            kwargs={"estudiante_id": self.estudiante_a.pk}
        )
        response = self.client.get(url)
        self.assertIn(response.status_code, [302, 403])

    def test_admin_a_no_puede_ver_historial_de_estudiante_b(self):
        """
        El admin del Colegio A intentando ver el historial de un estudiante
        del Colegio B debe recibir 404.
        """
        self.client.force_login(self.admin_a)
        url = reverse(
            "finanzas:historial_cuentas_estudiante",
            kwargs={"estudiante_id": self.estudiante_b.pk}
        )
        response = self.client.get(url)
        # La vista hace get_object_or_404 filtrando por institución del usuario
        self.assertEqual(
            response.status_code, 404,
            "Acceder al historial de un estudiante de otra institución debe devolver 404"
        )

    def test_admin_a_puede_ver_historial_de_su_estudiante(self):
        """El admin del Colegio A puede ver el historial de su propio estudiante."""
        self.client.force_login(self.admin_a)
        url = reverse(
            "finanzas:historial_cuentas_estudiante",
            kwargs={"estudiante_id": self.estudiante_a.pk}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class PagoRegistradoInstitucionTest(FinanzasMultiTenantBase):
    """Prueba que PagoRegistrado queda asociado a la institución correcta."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cuenta_a = CuentaPorCobrarEstudiante.objects.create(
            estudiante=cls.estudiante_a,
            concepto_pago=cls.concepto_a,
            monto_asignado=Decimal("500000.00"),
            fecha_vencimiento_especifica=datetime.date(2099, 12, 31),
        )
        cls.cuenta_b = CuentaPorCobrarEstudiante.objects.create(
            estudiante=cls.estudiante_b,
            concepto_pago=cls.concepto_b,
            monto_asignado=Decimal("400000.00"),
            fecha_vencimiento_especifica=datetime.date(2099, 12, 31),
        )

    def test_pago_hereda_institucion_de_la_cuenta(self):
        """
        Al crear un PagoRegistrado, la institución debe heredarse
        automáticamente de la CuentaPorCobrarEstudiante asociada.
        """
        pago = PagoRegistrado.objects.create(
            cuenta=self.cuenta_a,
            estudiante=self.estudiante_a,
            fecha_pago=datetime.date(2024, 2, 15),
            valor_pagado=Decimal("500000.00"),
            metodo_pago="EFECTIVO",
            registrado_por=self.admin_a,
        )

        self.assertEqual(
            pago.institucion, self.inst_a,
            "El PagoRegistrado debe heredar la institución de su cuenta"
        )
        self.assertNotEqual(
            pago.institucion, self.inst_b,
            "El PagoRegistrado del Colegio A no debe quedar con la institución B"
        )

    def test_pago_de_b_tiene_institucion_b(self):
        """Un pago sobre una cuenta del Colegio B debe quedar con institución B."""
        pago = PagoRegistrado.objects.create(
            cuenta=self.cuenta_b,
            estudiante=self.estudiante_b,
            fecha_pago=datetime.date(2024, 2, 15),
            valor_pagado=Decimal("400000.00"),
            metodo_pago="TRANSFERENCIA",
            registrado_por=self.admin_b,
        )

        self.assertEqual(pago.institucion, self.inst_b)

    def test_pagos_filtrados_por_institucion_son_disjuntos(self):
        """Los pagos de inst_a e inst_b no deben solaparse."""
        pago_a = PagoRegistrado.objects.create(
            cuenta=self.cuenta_a,
            estudiante=self.estudiante_a,
            fecha_pago=datetime.date(2024, 2, 15),
            valor_pagado=Decimal("250000.00"),
            metodo_pago="EFECTIVO",
        )
        pago_b = PagoRegistrado.objects.create(
            cuenta=self.cuenta_b,
            estudiante=self.estudiante_b,
            fecha_pago=datetime.date(2024, 2, 15),
            valor_pagado=Decimal("400000.00"),
            metodo_pago="TRANSFERENCIA",
        )

        pagos_a = set(
            PagoRegistrado.objects.filter(institucion=self.inst_a).values_list("pk", flat=True)
        )
        pagos_b = set(
            PagoRegistrado.objects.filter(institucion=self.inst_b).values_list("pk", flat=True)
        )

        self.assertTrue(pagos_a.isdisjoint(pagos_b))
        self.assertIn(pago_a.pk, pagos_a)
        self.assertIn(pago_b.pk, pagos_b)

    def test_cuenta_actualiza_estado_al_pagar_completo(self):
        """
        Después de registrar un pago completo, el estado de la cuenta
        debe actualizarse a PAGADO.
        """
        pago = PagoRegistrado.objects.create(
            cuenta=self.cuenta_a,
            estudiante=self.estudiante_a,
            fecha_pago=datetime.date(2024, 2, 15),
            valor_pagado=Decimal("500000.00"),
            metodo_pago="TRANSFERENCIA",
        )

        # Refrescar la cuenta desde la BD (la señal post_save la actualiza)
        self.cuenta_a.refresh_from_db()
        self.assertEqual(
            self.cuenta_a.estado, "PAGADO",
            "Después de pagar el monto completo, el estado debe ser PAGADO"
        )
