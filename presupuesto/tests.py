"""
Tests de integración del núcleo presupuestal (Fase 1).

Verifica:
1. La cadena completa Apropiación → CDP → RP → Obligación → Orden de Pago.
2. Que ningún eslabón puede superar el saldo disponible del anterior.
3. Aislamiento multi-institución (Colegio A no ve ni puede tocar datos del B).
4. Que una vigencia cerrada bloquea nuevos CDP.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from finanzas.models import InstitucionEducativa, Proveedor
from gestion_academica.models import Usuario

from . import services
from .models import Apropiacion, RubroPresupuestalGasto, VigenciaFiscal


def _crear_institucion(nombre, nit):
    inst = InstitucionEducativa(
        nombre=nombre, nit=nit, tipo_institucion='publico',
        google_api_key="test-key-placeholder",
        mp_webhook_secret="test-secret-placeholder",
    )
    inst.save()
    return inst


def _crear_usuario(username, email, institucion):
    return Usuario.objects.create_user(
        username=username, email=email, password="TestPass123!",
        rol='administrador', institucion_asociada=institucion, is_staff=True,
    )


class CicloPresupuestalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.inst_a = _crear_institucion("FSE Colegio A", "900111111-1")
        cls.inst_b = _crear_institucion("FSE Colegio B", "900222222-2")
        cls.user_a = _crear_usuario("admin_a_fse", "a@fse.test", cls.inst_a)
        cls.user_b = _crear_usuario("admin_b_fse", "b@fse.test", cls.inst_b)

        cls.vigencia_a = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)
        cls.rubro_a = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.1", nombre="Mantenimiento",
            tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO,
        )
        cls.apropiacion_a = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia_a, rubro=cls.rubro_a,
            valor_inicial=Decimal('1000000.00'),
        )
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Ferretería El Tornillo")

    def test_saldo_apropiacion_inicial(self):
        self.assertEqual(self.apropiacion_a.valor_definitivo, Decimal('1000000.00'))
        self.assertEqual(self.apropiacion_a.saldo_disponible, Decimal('1000000.00'))

    def test_cadena_completa_reduce_saldo_en_cascada(self):
        cdp = services.expedir_cdp(
            apropiacion=self.apropiacion_a, valor=Decimal('600000.00'),
            objeto="Mantenimiento de baños", usuario=self.user_a,
        )
        self.assertEqual(self.apropiacion_a.saldo_disponible, Decimal('400000.00'))

        rp = services.crear_rp(
            cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Reparación de tuberías",
            valor=Decimal('500000.00'), usuario=self.user_a,
        )
        self.assertEqual(cdp.saldo_disponible, Decimal('100000.00'))

        obligacion = services.causar_obligacion(rp=rp, valor=Decimal('500000.00'), soporte=None, usuario=self.user_a)
        self.assertEqual(rp.saldo_disponible, Decimal('0.00'))

        orden = services.generar_orden_pago(obligacion=obligacion, total_retenciones=Decimal('20000.00'), usuario=self.user_a)
        self.assertEqual(orden.valor_neto, Decimal('480000.00'))
        self.assertEqual(obligacion.saldo_disponible, Decimal('0.00'))

    def test_cdp_no_puede_superar_saldo_apropiacion(self):
        with self.assertRaises(ValidationError):
            services.expedir_cdp(
                apropiacion=self.apropiacion_a, valor=Decimal('2000000.00'),
                objeto="Algo carísimo", usuario=self.user_a,
            )

    def test_rp_no_puede_superar_saldo_cdp(self):
        cdp = services.expedir_cdp(
            apropiacion=self.apropiacion_a, valor=Decimal('300000.00'),
            objeto="Pintura", usuario=self.user_a,
        )
        with self.assertRaises(ValidationError):
            services.crear_rp(
                cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Compra de pintura",
                valor=Decimal('400000.00'), usuario=self.user_a,
            )

    def test_obligacion_no_puede_superar_saldo_rp(self):
        cdp = services.expedir_cdp(apropiacion=self.apropiacion_a, valor=Decimal('300000.00'), objeto="X", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Y", valor=Decimal('300000.00'), usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.causar_obligacion(rp=rp, valor=Decimal('350000.00'), soporte=None, usuario=self.user_a)

    def test_vigencia_cerrada_bloquea_nuevo_cdp(self):
        services.cerrar_vigencia(vigencia=self.vigencia_a, usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.expedir_cdp(
                apropiacion=self.apropiacion_a, valor=Decimal('10000.00'),
                objeto="Ya no debería poder", usuario=self.user_a,
            )

    def test_aislamiento_multi_institucion(self):
        """Un CDP de la institución A no debe ser visible al filtrar por B."""
        services.expedir_cdp(apropiacion=self.apropiacion_a, valor=Decimal('100000.00'), objeto="X", usuario=self.user_a)
        from .models import CDP
        self.assertEqual(CDP.objects.filter(institucion=self.inst_b).count(), 0)
        self.assertEqual(CDP.objects.filter(institucion=self.inst_a).count(), 1)

    def test_vista_dashboard_requiere_login(self):
        from django.urls import reverse
        response = self.client.get(reverse('presupuesto:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_docente_no_puede_gestionar_presupuesto(self):
        docente = Usuario.objects.create_user(
            username="docente_fse", email="d@fse.test", password="TestPass123!",
            rol='docente', institucion_asociada=self.inst_a,
        )
        self.client.force_login(docente)
        from django.urls import reverse
        response = self.client.get(reverse('presupuesto:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse('presupuesto:dashboard'))
