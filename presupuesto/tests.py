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
    from django.utils import timezone
    from gestion_academica.legal import POLITICA_TRATAMIENTO_DATOS_VERSION
    return Usuario.objects.create_user(
        username=username, email=email, password="TestPass123!",
        rol='administrador', institucion_asociada=institucion, is_staff=True,
        acepto_tratamiento_datos=True, fecha_aceptacion_tratamiento_datos=timezone.now(),
        version_politica_aceptada=POLITICA_TRATAMIENTO_DATOS_VERSION,
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

        orden = services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)
        self.assertEqual(orden.valor_neto, Decimal('500000.00'))
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


class ContabilidadYRetencionesTest(TestCase):
    """Fase 2: causación contable (partida doble) y retenciones."""

    @classmethod
    def setUpTestData(cls):
        from .models import CatalogoGeneralCuentas

        cls.inst_a = _crear_institucion("FSE Contab A", "900333333-3")
        cls.user_a = _crear_usuario("admin_contab_a", "contaba@fse.test", cls.inst_a)
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Papelería La Central")

        cls.cuenta_gasto = CatalogoGeneralCuentas.objects.create(codigo='5120-T', nombre='Materiales y suministros', naturaleza='DEBITO')
        cls.cuenta_bancos = CatalogoGeneralCuentas.objects.create(codigo='1110-T', nombre='Bancos', naturaleza='DEBITO')
        cls.cuenta_retefuente = CatalogoGeneralCuentas.objects.create(codigo='2436-T', nombre='ReteFuente por pagar', naturaleza='CREDITO')

        cls.vigencia = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)
        cls.rubro = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.2", nombre="Papelería",
            tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO, cuenta_cgc_gasto=cls.cuenta_gasto,
        )
        cls.apropiacion = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia, rubro=cls.rubro, valor_inicial=Decimal('1000000.00'),
        )

    def _crear_orden_pago(self, valor=Decimal('500000.00')):
        cdp = services.expedir_cdp(apropiacion=self.apropiacion, valor=valor, objeto="Papelería", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Compra papelería", valor=valor, usuario=self.user_a)
        obligacion = services.causar_obligacion(rp=rp, valor=valor, soporte=None, usuario=self.user_a)
        return services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)

    def test_orden_pago_nace_sin_retenciones(self):
        orden = self._crear_orden_pago()
        self.assertEqual(orden.total_retenciones, Decimal('0.00'))
        self.assertEqual(orden.valor_neto, orden.valor_bruto)

    def test_agregar_retencion_recalcula_neto(self):
        from .models import ConceptoRetencion
        orden = self._crear_orden_pago(Decimal('500000.00'))
        concepto = ConceptoRetencion.objects.create(
            institucion=self.inst_a, tipo=ConceptoRetencion.Tipo.RETEFUENTE, nombre='ReteFuente compras',
            tarifa_porcentaje=Decimal('2.5'), cuenta_puc_pasivo=self.cuenta_retefuente,
        )
        services.agregar_retencion(orden_pago=orden, concepto=concepto, base_gravable=Decimal('500000.00'), usuario=self.user_a)
        orden.refresh_from_db()
        self.assertEqual(orden.total_retenciones, Decimal('12500.00'))
        self.assertEqual(orden.valor_neto, Decimal('487500.00'))

    def test_retencion_no_puede_superar_valor_bruto(self):
        from .models import ConceptoRetencion
        orden = self._crear_orden_pago(Decimal('100000.00'))
        concepto = ConceptoRetencion.objects.create(
            institucion=self.inst_a, tipo=ConceptoRetencion.Tipo.RETEFUENTE, nombre='ReteFuente enorme',
            tarifa_porcentaje=Decimal('150'), cuenta_puc_pasivo=self.cuenta_retefuente,
        )
        with self.assertRaises(ValidationError):
            services.agregar_retencion(orden_pago=orden, concepto=concepto, base_gravable=Decimal('100000.00'), usuario=self.user_a)

    def test_comprobante_queda_cuadrado_y_contabilizable(self):
        from .models import ConceptoRetencion
        orden = self._crear_orden_pago(Decimal('500000.00'))
        concepto = ConceptoRetencion.objects.create(
            institucion=self.inst_a, tipo=ConceptoRetencion.Tipo.RETEFUENTE, nombre='ReteFuente compras',
            tarifa_porcentaje=Decimal('2.5'), cuenta_puc_pasivo=self.cuenta_retefuente,
        )
        services.agregar_retencion(orden_pago=orden, concepto=concepto, base_gravable=Decimal('500000.00'), usuario=self.user_a)
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancos=self.cuenta_bancos, usuario=self.user_a)
        self.assertTrue(comprobante.esta_cuadrado)
        self.assertEqual(comprobante.total_debitos, Decimal('500000.00'))
        self.assertEqual(comprobante.total_creditos, Decimal('500000.00'))

        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        comprobante.refresh_from_db()
        orden.refresh_from_db()
        self.assertEqual(comprobante.estado, 'CONTABILIZADO')
        self.assertEqual(orden.estado, 'PAGADA')

    def test_no_se_puede_generar_comprobante_sin_cuenta_configurada_en_rubro(self):
        rubro_sin_cuenta = RubroPresupuestalGasto.objects.create(
            institucion=self.inst_a, codigo="2.3.9", nombre="Sin cuenta configurada",
            tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO,
        )
        apropiacion = Apropiacion.objects.create(
            institucion=self.inst_a, vigencia=self.vigencia, rubro=rubro_sin_cuenta, valor_inicial=Decimal('200000.00'),
        )
        cdp = services.expedir_cdp(apropiacion=apropiacion, valor=Decimal('100000.00'), objeto="X", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Y", valor=Decimal('100000.00'), usuario=self.user_a)
        obligacion = services.causar_obligacion(rp=rp, valor=Decimal('100000.00'), soporte=None, usuario=self.user_a)
        orden = services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.generar_comprobante_contable(orden_pago=orden, cuenta_bancos=self.cuenta_bancos, usuario=self.user_a)

    def test_no_se_puede_contabilizar_dos_veces(self):
        orden = self._crear_orden_pago()
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancos=self.cuenta_bancos, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)

    def test_reversar_comprobante_crea_ajuste_con_movimientos_invertidos(self):
        orden = self._crear_orden_pago()
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancos=self.cuenta_bancos, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)

        reverso = services.reversar_comprobante(comprobante=comprobante, usuario=self.user_a, motivo="Error en el beneficiario")
        self.assertEqual(reverso.tipo, 'AJUSTE')
        self.assertEqual(reverso.estado, 'CONTABILIZADO')
        self.assertTrue(reverso.esta_cuadrado)
        # El movimiento original debitaba el gasto; el reverso debe acreditarlo por el mismo valor.
        mov_original = comprobante.movimientos.get(cuenta=self.cuenta_gasto)
        mov_reverso = reverso.movimientos.get(cuenta=self.cuenta_gasto)
        self.assertEqual(mov_reverso.valor_credito, mov_original.valor_debito)

    def test_no_se_puede_anular_orden_con_comprobante_generado(self):
        from django.urls import reverse
        orden = self._crear_orden_pago()
        services.generar_comprobante_contable(orden_pago=orden, cuenta_bancos=self.cuenta_bancos, usuario=self.user_a)
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('presupuesto:anular_orden_pago', args=[orden.pk]), {'motivo': 'x'})
        orden.refresh_from_db()
        self.assertNotEqual(orden.estado, 'ANULADA')
