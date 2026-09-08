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
        from .models import CatalogoGeneralCuentas, CuentaBancaria

        cls.inst_a = _crear_institucion("FSE Contab A", "900333333-3")
        cls.user_a = _crear_usuario("admin_contab_a", "contaba@fse.test", cls.inst_a)
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Papelería La Central")

        cls.cuenta_gasto = CatalogoGeneralCuentas.objects.create(codigo='5120-T', nombre='Materiales y suministros', naturaleza='DEBITO')
        cls.cuenta_bancos = CatalogoGeneralCuentas.objects.create(codigo='1110-T', nombre='Bancos', naturaleza='DEBITO')
        cls.cuenta_retefuente = CatalogoGeneralCuentas.objects.create(codigo='2436-T', nombre='ReteFuente por pagar', naturaleza='CREDITO')
        cls.cuenta_bancaria = CuentaBancaria.objects.create(
            institucion=cls.inst_a, banco='Banco de Pruebas', numero_cuenta='0001-T',
            cuenta_cgc=cls.cuenta_bancos, saldo_inicial=Decimal('10000000.00'),
        )

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
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
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
            services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)

    def test_no_se_puede_contabilizar_dos_veces(self):
        orden = self._crear_orden_pago()
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)

    def test_reversar_comprobante_crea_ajuste_con_movimientos_invertidos(self):
        orden = self._crear_orden_pago()
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
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
        services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        self.client.force_login(self.user_a)
        response = self.client.post(reverse('presupuesto:anular_orden_pago', args=[orden.pk]), {'motivo': 'x'})
        orden.refresh_from_db()
        self.assertNotEqual(orden.estado, 'ANULADA')


class CatalogosOficialesTest(TestCase):
    """Catálogos globales sembrados por migración: Fuentes de Financiación
    (CHIP/CGN) y Categoría CPC (DANE). Ambos son catálogos de referencia sin
    institución — se sirven a través de las migraciones de datos, no se
    crean aquí."""

    @classmethod
    def setUpTestData(cls):
        cls.inst_a = _crear_institucion("FSE Colegio Catálogos", "900333333-3")
        cls.user_a = _crear_usuario("admin_catalogos", "cat@fse.test", cls.inst_a)
        cls.vigencia_a = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)
        cls.rubro_gasto = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.2", nombre="Materiales",
            tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO,
        )
        cls.apropiacion = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia_a, rubro=cls.rubro_gasto,
            valor_inicial=Decimal('1000000.00'),
        )
        cls.proveedor = Proveedor.objects.create(institucion=cls.inst_a, nombre="Papelería Central")

    def test_fuentes_de_financiacion_sembradas(self):
        from .models import FuenteFinanciacion
        self.assertEqual(FuenteFinanciacion.objects.count(), 230)
        self.assertTrue(
            FuenteFinanciacion.objects.filter(aplica_establecimientos_publicos_territoriales=True).exists()
        )

    def test_categoria_cpc_sembrada(self):
        from .models import CategoriaCPC
        self.assertEqual(CategoriaCPC.objects.count(), 9933)
        self.assertEqual(CategoriaCPC.objects.filter(tipo='BIEN').count(), 8254)
        self.assertEqual(CategoriaCPC.objects.filter(tipo='SERVICIO').count(), 1679)

    def test_buscar_categoria_cpc_requiere_al_menos_dos_caracteres(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('presupuesto:buscar_categoria_cpc'), {'q': 'a'})
        self.assertEqual(response.json(), {'resultados': []})

    def test_buscar_categoria_cpc_encuentra_por_titulo(self):
        from django.urls import reverse
        from .models import CategoriaCPC
        objetivo = CategoriaCPC.objects.filter(titulo__icontains='computador').first()
        self.assertIsNotNone(objetivo, "el catálogo real debería traer al menos un 'computador'")
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('presupuesto:buscar_categoria_cpc'), {'q': 'computador'})
        data = response.json()
        self.assertTrue(any(r['id'] == objetivo.pk for r in data['resultados']))

    def test_rp_puede_llevar_categoria_cpc(self):
        from .models import CategoriaCPC
        cat = CategoriaCPC.objects.first()
        cdp = services.expedir_cdp(
            apropiacion=self.apropiacion, valor=Decimal('300000.00'),
            objeto="Compra de materiales", usuario=self.user_a,
        )
        rp = services.crear_rp(
            cdp=cdp, tercero=self.proveedor, objeto_contrato="Resmas de papel",
            categoria_cpc=cat, valor=Decimal('200000.00'), usuario=self.user_a,
        )
        self.assertEqual(rp.categoria_cpc, cat)


class TesoreriaYAlmacenTest(TestCase):
    """Fase 3: cuentas bancarias reales (saldo movido por MovimientoTesoreria,
    nunca editado a mano) y almacén básico (stock por MovimientoAlmacen)."""

    @classmethod
    def setUpTestData(cls):
        from .models import CatalogoGeneralCuentas, CuentaBancaria, ElementoAlmacen

        cls.inst_a = _crear_institucion("FSE Tesoreria A", "900444444-4")
        cls.user_a = _crear_usuario("admin_tesoreria_a", "tesoreria@fse.test", cls.inst_a)
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Ferretería Central")

        cls.cuenta_gasto = CatalogoGeneralCuentas.objects.create(codigo='5120-T2', nombre='Materiales', naturaleza='DEBITO')
        cls.cuenta_bancos_cgc = CatalogoGeneralCuentas.objects.create(codigo='1110-T2', nombre='Bancos', naturaleza='DEBITO')
        cls.cuenta_bancaria = CuentaBancaria.objects.create(
            institucion=cls.inst_a, banco='Banco Popular', numero_cuenta='1234-T',
            cuenta_cgc=cls.cuenta_bancos_cgc, saldo_inicial=Decimal('300000.00'),
        )
        cls.vigencia = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)
        cls.rubro = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.3", nombre="Ferretería",
            tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO, cuenta_cgc_gasto=cls.cuenta_gasto,
        )
        cls.apropiacion = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia, rubro=cls.rubro, valor_inicial=Decimal('1000000.00'),
        )
        cls.elemento = ElementoAlmacen.objects.create(
            institucion=cls.inst_a, codigo='EL-001', nombre='Resma de papel carta', stock_minimo=5,
        )

    def _crear_orden_pago(self, valor):
        cdp = services.expedir_cdp(apropiacion=self.apropiacion, valor=valor, objeto="Compra", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Compra ferretería", valor=valor, usuario=self.user_a)
        obligacion = services.causar_obligacion(rp=rp, valor=valor, soporte=None, usuario=self.user_a)
        return services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)

    def test_cuenta_bancaria_saldo_inicial(self):
        self.assertEqual(self.cuenta_bancaria.saldo_actual, Decimal('300000.00'))

    def test_contabilizar_comprobante_reduce_saldo_bancario(self):
        orden = self._crear_orden_pago(Decimal('100000.00'))
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        self.cuenta_bancaria.refresh_from_db()
        self.assertEqual(self.cuenta_bancaria.saldo_actual, Decimal('200000.00'))

    def test_contabilizar_bloquea_si_saldo_insuficiente(self):
        orden = self._crear_orden_pago(Decimal('500000.00'))
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        with self.assertRaises(ValidationError):
            services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)

    def test_reversar_comprobante_restaura_saldo_bancario(self):
        orden = self._crear_orden_pago(Decimal('100000.00'))
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        self.cuenta_bancaria.refresh_from_db()
        self.assertEqual(self.cuenta_bancaria.saldo_actual, Decimal('200000.00'))

        services.reversar_comprobante(comprobante=comprobante, usuario=self.user_a, motivo="Se anuló la compra")
        self.cuenta_bancaria.refresh_from_db()
        self.assertEqual(self.cuenta_bancaria.saldo_actual, Decimal('300000.00'))

    def test_movimiento_almacen_entrada_y_salida_calculan_stock(self):
        from .models import MovimientoAlmacen
        services.registrar_movimiento_almacen(
            elemento=self.elemento, tipo=MovimientoAlmacen.Tipo.ENTRADA, cantidad=10,
            valor_unitario=Decimal('2000.00'), usuario=self.user_a,
        )
        self.assertEqual(self.elemento.stock_actual, 10)
        services.registrar_movimiento_almacen(
            elemento=self.elemento, tipo=MovimientoAlmacen.Tipo.SALIDA, cantidad=4,
            responsable="Docente Juana Pérez", usuario=self.user_a,
        )
        self.assertEqual(self.elemento.stock_actual, 6)

    def test_movimiento_almacen_salida_no_puede_superar_stock(self):
        from .models import MovimientoAlmacen
        with self.assertRaises(ValidationError):
            services.registrar_movimiento_almacen(
                elemento=self.elemento, tipo=MovimientoAlmacen.Tipo.SALIDA, cantidad=1, usuario=self.user_a,
            )


class ReportesEjecucionTest(TestCase):
    """Fase 4: reportes de ejecución presupuestal (CHIP/SIA) y consolidación."""

    @classmethod
    def setUpTestData(cls):
        from .models import (
            CatalogoGeneralCuentas, CuentaBancaria, FuenteFinanciacion, PresupuestoIngreso,
            RubroPresupuestalIngreso,
        )

        cls.inst_a = _crear_institucion("FSE Reportes A", "900555555-5")
        cls.user_a = _crear_usuario("admin_reportes_a", "reportes@fse.test", cls.inst_a)
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Distribuidora Escolar")

        cls.fuente = FuenteFinanciacion.objects.first()
        cls.vigencia = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)

        cls.rubro_ingreso = RubroPresupuestalIngreso.objects.create(
            institucion=cls.inst_a, codigo="1.1", nombre="SGP", tipo_recurso=cls.fuente,
        )
        cls.presupuesto_ingreso = PresupuestoIngreso.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia, rubro=cls.rubro_ingreso, valor_inicial=Decimal('1000000.00'),
        )

        cls.cuenta_gasto = CatalogoGeneralCuentas.objects.create(codigo='5120-R', nombre='Materiales', naturaleza='DEBITO')
        cls.cuenta_bancos_cgc = CatalogoGeneralCuentas.objects.create(codigo='1110-R', nombre='Bancos', naturaleza='DEBITO')
        cls.cuenta_bancaria = CuentaBancaria.objects.create(
            institucion=cls.inst_a, banco='Banco Reportes', numero_cuenta='777-1',
            cuenta_cgc=cls.cuenta_bancos_cgc, saldo_inicial=Decimal('5000000.00'),
        )
        cls.rubro_gasto = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.5", nombre="Materiales", tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO,
            cuenta_cgc_gasto=cls.cuenta_gasto,
        )
        cls.apropiacion = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia, rubro=cls.rubro_gasto, valor_inicial=Decimal('500000.00'),
        )

    def test_registrar_recaudo_suma_al_valor_recaudado(self):
        services.registrar_recaudo(presupuesto_ingreso=self.presupuesto_ingreso, valor=Decimal('300000.00'), usuario=self.user_a)
        services.registrar_recaudo(presupuesto_ingreso=self.presupuesto_ingreso, valor=Decimal('50000.00'), usuario=self.user_a)
        self.presupuesto_ingreso.refresh_from_db()
        self.assertEqual(self.presupuesto_ingreso.valor_recaudado, Decimal('350000.00'))

    def test_registrar_recaudo_rechaza_valor_no_positivo(self):
        with self.assertRaises(ValidationError):
            services.registrar_recaudo(presupuesto_ingreso=self.presupuesto_ingreso, valor=Decimal('0.00'), usuario=self.user_a)

    def test_ejecucion_ingresos_refleja_recaudo(self):
        from . import reportes
        services.registrar_recaudo(presupuesto_ingreso=self.presupuesto_ingreso, valor=Decimal('400000.00'), usuario=self.user_a)
        filas = reportes.ejecucion_ingresos(self.vigencia)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]['presupuestado'], Decimal('1000000.00'))
        self.assertEqual(filas[0]['recaudado'], Decimal('400000.00'))
        self.assertEqual(filas[0]['saldo_por_recaudar'], Decimal('600000.00'))
        self.assertEqual(filas[0]['fuente_financiacion'], self.fuente)

    def test_ejecucion_gastos_refleja_cadena_completa(self):
        from . import reportes
        cdp = services.expedir_cdp(apropiacion=self.apropiacion, valor=Decimal('300000.00'), objeto="Compra", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Materiales", valor=Decimal('250000.00'), usuario=self.user_a)
        obligacion = services.causar_obligacion(rp=rp, valor=Decimal('250000.00'), soporte=None, usuario=self.user_a)
        orden = services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)
        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)

        filas = reportes.ejecucion_gastos(self.vigencia)
        self.assertEqual(len(filas), 1)
        fila = filas[0]
        self.assertEqual(fila['apropiacion_definitiva'], Decimal('500000.00'))
        self.assertEqual(fila['comprometido'], Decimal('250000.00'))
        self.assertEqual(fila['obligado'], Decimal('250000.00'))
        self.assertEqual(fila['pagado'], Decimal('250000.00'))
        self.assertEqual(fila['saldo_por_comprometer'], Decimal('250000.00'))

    def test_balance_comprobacion_solo_incluye_contabilizados(self):
        from . import reportes
        cdp = services.expedir_cdp(apropiacion=self.apropiacion, valor=Decimal('100000.00'), objeto="Compra", usuario=self.user_a)
        rp = services.crear_rp(cdp=cdp, tercero=self.proveedor_a, objeto_contrato="Materiales", valor=Decimal('100000.00'), usuario=self.user_a)
        obligacion = services.causar_obligacion(rp=rp, valor=Decimal('100000.00'), soporte=None, usuario=self.user_a)
        orden = services.generar_orden_pago(obligacion=obligacion, usuario=self.user_a)
        comprobante = services.generar_comprobante_contable(orden_pago=orden, cuenta_bancaria=self.cuenta_bancaria, usuario=self.user_a)

        # Aún en Borrador: no debe aparecer en el balance.
        filas = reportes.balance_comprobacion(self.vigencia)
        self.assertEqual(len(filas), 0)

        services.contabilizar_comprobante(comprobante=comprobante, usuario=self.user_a)
        filas = reportes.balance_comprobacion(self.vigencia)
        codigos = {f['cuenta__codigo']: f for f in filas}
        self.assertIn('5120-R', codigos)
        self.assertEqual(codigos['5120-R']['total_debitos'], Decimal('100000.00'))
        self.assertEqual(codigos['5120-R']['saldo'], Decimal('100000.00'))

    def test_vista_reportes_requiere_login(self):
        from django.urls import reverse
        response = self.client.get(reverse('presupuesto:reporte_ejecucion'))
        self.assertEqual(response.status_code, 302)

    def test_vista_reportes_renderiza_para_gestor(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('presupuesto:reporte_ejecucion'))
        self.assertEqual(response.status_code, 200)

    def test_exportar_excel_devuelve_xlsx(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('presupuesto:exportar_reporte_ejecucion_excel'), {'vigencia': self.vigencia.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    def test_exportar_pdf_devuelve_pdf(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('presupuesto:exportar_reporte_ejecucion_pdf'), {'vigencia': self.vigencia.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))


class DocumentosImprimiblesTest(TestCase):
    """Cada documento del ciclo (CDP, RP, Obligación, Orden de Pago,
    Comprobante) debe poder imprimirse en PDF, y solo por instituciones
    con acceso al documento (IDOR)."""

    @classmethod
    def setUpTestData(cls):
        from .models import CatalogoGeneralCuentas, CuentaBancaria

        cls.inst_a = _crear_institucion("FSE Imprimibles A", "900666666-6")
        cls.inst_b = _crear_institucion("FSE Imprimibles B", "900777777-7")
        cls.user_a = _crear_usuario("admin_imprimibles_a", "imp_a@fse.test", cls.inst_a)
        cls.user_b = _crear_usuario("admin_imprimibles_b", "imp_b@fse.test", cls.inst_b)
        cls.proveedor_a = Proveedor.objects.create(institucion=cls.inst_a, nombre="Ferretería El Martillo")

        cls.cuenta_gasto = CatalogoGeneralCuentas.objects.create(codigo='5120-I', nombre='Materiales', naturaleza='DEBITO')
        cls.cuenta_bancos_cgc = CatalogoGeneralCuentas.objects.create(codigo='1110-I', nombre='Bancos', naturaleza='DEBITO')
        cls.cuenta_bancaria = CuentaBancaria.objects.create(
            institucion=cls.inst_a, banco='Banco Imprimibles', numero_cuenta='555-1',
            cuenta_cgc=cls.cuenta_bancos_cgc, saldo_inicial=Decimal('5000000.00'),
        )
        cls.vigencia = VigenciaFiscal.objects.create(institucion=cls.inst_a, anio=2026)
        cls.rubro = RubroPresupuestalGasto.objects.create(
            institucion=cls.inst_a, codigo="2.3.7", nombre="Ferretería", tipo=RubroPresupuestalGasto.Tipo.FUNCIONAMIENTO,
            cuenta_cgc_gasto=cls.cuenta_gasto,
        )
        cls.apropiacion = Apropiacion.objects.create(
            institucion=cls.inst_a, vigencia=cls.vigencia, rubro=cls.rubro, valor_inicial=Decimal('1000000.00'),
        )
        cls.cdp = services.expedir_cdp(apropiacion=cls.apropiacion, valor=Decimal('500000.00'), objeto="Compra", usuario=cls.user_a)
        cls.rp = services.crear_rp(cdp=cls.cdp, tercero=cls.proveedor_a, objeto_contrato="Materiales varios", valor=Decimal('400000.00'), usuario=cls.user_a)
        cls.obligacion = services.causar_obligacion(rp=cls.rp, valor=Decimal('400000.00'), soporte=None, usuario=cls.user_a)
        cls.orden = services.generar_orden_pago(obligacion=cls.obligacion, usuario=cls.user_a)
        cls.comprobante = services.generar_comprobante_contable(orden_pago=cls.orden, cuenta_bancaria=cls.cuenta_bancaria, usuario=cls.user_a)

    def _assert_es_pdf(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_imprimir_cdp(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        self._assert_es_pdf(self.client.get(reverse('presupuesto:imprimir_cdp', args=[self.cdp.pk])))

    def test_imprimir_rp(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        self._assert_es_pdf(self.client.get(reverse('presupuesto:imprimir_rp', args=[self.rp.pk])))

    def test_imprimir_obligacion(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        self._assert_es_pdf(self.client.get(reverse('presupuesto:imprimir_obligacion', args=[self.obligacion.pk])))

    def test_imprimir_orden_pago(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        self._assert_es_pdf(self.client.get(reverse('presupuesto:imprimir_orden_pago', args=[self.orden.pk])))

    def test_imprimir_comprobante(self):
        from django.urls import reverse
        self.client.force_login(self.user_a)
        self._assert_es_pdf(self.client.get(reverse('presupuesto:imprimir_comprobante', args=[self.comprobante.pk])))

    def test_institucion_b_no_puede_imprimir_documentos_de_a(self):
        """IDOR: la institución B no debe poder imprimir documentos de la A."""
        from django.urls import reverse
        self.client.force_login(self.user_b)
        for url_name, pk in [
            ('imprimir_cdp', self.cdp.pk), ('imprimir_rp', self.rp.pk),
            ('imprimir_obligacion', self.obligacion.pk), ('imprimir_orden_pago', self.orden.pk),
            ('imprimir_comprobante', self.comprobante.pk),
        ]:
            response = self.client.get(reverse(f'presupuesto:{url_name}', args=[pk]))
            self.assertEqual(response.status_code, 404, f'{url_name} debería dar 404 para otra institución')
