"""
Seed migration: banco público de ejercicios (nivel Básico) para los 18 DBA
de Matemáticas del piloto (grados 3°-5°) — 5 ejercicios por DBA (90 en
total), es_publica=True / institucion=None, mismo patrón que
simulacros/migrations/0002_seed_banco_preguntas.py.

Antes de esta siembra, solo 1 de los 18 DBA tenía ejercicios (generados a
mano por una institución concreta, es_publica=False) — el resto mostraba
"Aún no hay ejercicios disponibles" a cualquier estudiante. Con esto, todas
las instituciones tienen contenido de partida en nivel Básico para
practicar cualquiera de los 18 DBA; Medio/Alto se pueden ampliar después
(a mano por cada colegio con "Generar con IA", o en una siembra pública
posterior).

DBAPredefinido NO se crea en una migración (se carga aparte con
`python manage.py cargar_dba`, ver gestion_academica/management/commands/
cargar_dba.py) — así que esta siembra busca cada DBA por (area, grado,
numero) y omite silenciosamente los que no existan todavía en vez de
fallar, para no romper `migrate` en un entorno donde el catálogo de DBA
aún no se cargó.
"""
import logging

from django.db import migrations

logger = logging.getLogger(__name__)


# grado, numero → 5 ejercicios de opción única, nivel BASICO
EJERCICIOS = {
    ('3', 1): [  # Numeración decimal hasta 9.999
        {
            "enunciado": "¿Cómo se escribe con cifras el número cuatro mil doscientos quince?",
            "opciones": [("A", "4.215", True), ("B", "4.125", False), ("C", "4.512", False), ("D", "40.215", False)],
            "explicacion": "Cuatro mil = 4.000, doscientos = 200, quince = 15. En total: 4.215.",
        },
        {
            "enunciado": "En el número 6.384, ¿qué cifra ocupa el lugar de las centenas?",
            "opciones": [("A", "6", False), ("B", "3", True), ("C", "8", False), ("D", "4", False)],
            "explicacion": "6 son unidades de mil, 3 son centenas, 8 son decenas y 4 son unidades.",
        },
        {
            "enunciado": "Andrés anotó estos números: 3.560, 3.056, 3.605 y 3.650. ¿Cuál es el mayor?",
            "opciones": [("A", "3.560", False), ("B", "3.056", False), ("C", "3.605", False), ("D", "3.650", True)],
            "explicacion": "Comparando cifra por cifra desde la izquierda, 3.650 tiene la mayor decena entre los que comparten la centena 6.",
        },
        {
            "enunciado": "El número 5.283 se puede descomponer como:",
            "opciones": [
                ("A", "5 unidades de mil + 2 centenas + 8 decenas + 3 unidades", True),
                ("B", "5 centenas + 2 decenas + 8 unidades + 3 unidades de mil", False),
                ("C", "5 decenas + 2 unidades + 8 centenas + 3 unidades de mil", False),
                ("D", "5 unidades + 2 decenas + 8 centenas + 3 unidades de mil", False),
            ],
            "explicacion": "Cada cifra del número corresponde a su valor posicional: 5(UM) 2(C) 8(D) 3(U).",
        },
        {
            "enunciado": "En la recta numérica, ¿qué número está ubicado exactamente entre 2.400 y 2.600?",
            "opciones": [("A", "2.450", False), ("B", "2.500", True), ("C", "2.550", False), ("D", "2.300", False)],
            "explicacion": "El punto medio entre 2.400 y 2.600 es 2.500.",
        },
    ],
    ('3', 2): [  # Cuatro operaciones básicas
        {
            "enunciado": "En un álbum, Camilo tiene 1.250 láminas pegadas y su hermana le regala 340 más. ¿Cuántas láminas tiene ahora en total?",
            "opciones": [("A", "1.590", True), ("B", "1.610", False), ("C", "910", False), ("D", "1.690", False)],
            "explicacion": "1.250 + 340 = 1.590.",
        },
        {
            "enunciado": "Una tienda tenía 2.800 cuadernos y vendió 1.150. ¿Cuántos cuadernos le quedan?",
            "opciones": [("A", "1.650", True), ("B", "1.750", False), ("C", "3.950", False), ("D", "1.550", False)],
            "explicacion": "2.800 − 1.150 = 1.650.",
        },
        {
            "enunciado": "Si cada caja tiene 8 paquetes de galletas y hay 6 cajas, ¿cuántos paquetes de galletas hay en total?",
            "opciones": [("A", "42", False), ("B", "48", True), ("C", "14", False), ("D", "56", False)],
            "explicacion": "8 × 6 = 48.",
        },
        {
            "enunciado": "Valentina repartió 45 dulces en partes iguales entre 5 amigas. ¿Cuántos dulces recibió cada una?",
            "opciones": [("A", "8", False), ("B", "9", True), ("C", "10", False), ("D", "7", False)],
            "explicacion": "45 ÷ 5 = 9.",
        },
        {
            "enunciado": "Un bus escolar hace 3 viajes al día y en cada viaje transporta 24 estudiantes. ¿Cuántos estudiantes transporta en total al día?",
            "opciones": [("A", "27", False), ("B", "72", True), ("C", "62", False), ("D", "48", False)],
            "explicacion": "24 × 3 = 72.",
        },
    ],
    ('3', 3): [  # Fracciones — parte de un entero, comparar, sumar homogéneas, recta numérica
        {
            "enunciado": "Una pizza se dividió en 8 partes iguales y Juan se comió 3 partes. ¿Qué fracción de la pizza comió Juan?",
            "opciones": [("A", "3/8", True), ("B", "8/3", False), ("C", "5/8", False), ("D", "3/5", False)],
            "explicacion": "Comió 3 de las 8 partes iguales: 3/8.",
        },
        {
            "enunciado": "¿Cuál de estas fracciones es mayor: 3/5 o 4/5?",
            "opciones": [("A", "3/5", False), ("B", "4/5", True), ("C", "Son iguales", False), ("D", "No se puede saber", False)],
            "explicacion": "Con el mismo denominador, es mayor la fracción con mayor numerador.",
        },
        {
            "enunciado": "En una caja hay 6 canicas azules de un total de 10. ¿Qué fracción representa las canicas azules?",
            "opciones": [("A", "6/10", True), ("B", "10/6", False), ("C", "4/10", False), ("D", "6/4", False)],
            "explicacion": "6 canicas azules de 10 en total: 6/10.",
        },
        {
            "enunciado": "María comió 2/6 de una barra de chocolate y luego comió 1/6 más. ¿Qué fracción de la barra comió en total?",
            "opciones": [("A", "3/12", False), ("B", "3/6", True), ("C", "2/12", False), ("D", "1/6", False)],
            "explicacion": "Con el mismo denominador se suman los numeradores: 2/6 + 1/6 = 3/6.",
        },
        {
            "enunciado": "En la recta numérica de 0 a 1 dividida en 4 partes iguales, ¿qué fracción corresponde al punto que está justo a la mitad?",
            "opciones": [("A", "1/4", False), ("B", "2/4", True), ("C", "3/4", False), ("D", "4/4", False)],
            "explicacion": "El punto medio entre 0 y 1, dividido en cuartos, es 2/4 (equivalente a 1/2).",
        },
    ],
    ('3', 4): [  # Figuras geométricas 2D/3D
        {
            "enunciado": "¿Cuántos lados tiene un pentágono?",
            "opciones": [("A", "4", False), ("B", "5", True), ("C", "6", False), ("D", "3", False)],
            "explicacion": "El prefijo 'penta' significa cinco: el pentágono tiene 5 lados.",
        },
        {
            "enunciado": "Un ángulo que mide exactamente 90° se llama:",
            "opciones": [("A", "Agudo", False), ("B", "Recto", True), ("C", "Obtuso", False), ("D", "Llano", False)],
            "explicacion": "Un ángulo de exactamente 90° es un ángulo recto.",
        },
        {
            "enunciado": "¿Cuántas caras tiene un cubo?",
            "opciones": [("A", "4", False), ("B", "6", True), ("C", "8", False), ("D", "12", False)],
            "explicacion": "Un cubo tiene 6 caras cuadradas.",
        },
        {
            "enunciado": "Una figura con todos sus ángulos menores de 90° tiene ángulos:",
            "opciones": [("A", "Rectos", False), ("B", "Obtusos", False), ("C", "Agudos", True), ("D", "Llanos", False)],
            "explicacion": "Los ángulos menores de 90° se llaman agudos.",
        },
        {
            "enunciado": "¿Cuántos vértices tiene una pirámide de base cuadrada?",
            "opciones": [("A", "4", False), ("B", "5", True), ("C", "6", False), ("D", "8", False)],
            "explicacion": "4 vértices de la base cuadrada más 1 vértice superior: 5 en total.",
        },
    ],
    ('3', 5): [  # Medición — longitud, perímetro, área
        {
            "enunciado": "¿Cuántos centímetros hay en 1 metro?",
            "opciones": [("A", "10", False), ("B", "100", True), ("C", "1.000", False), ("D", "50", False)],
            "explicacion": "1 metro equivale a 100 centímetros.",
        },
        {
            "enunciado": "Un terreno rectangular mide 6 metros de largo y 4 metros de ancho. ¿Cuál es su perímetro?",
            "opciones": [("A", "20 metros", True), ("B", "24 metros", False), ("C", "10 metros", False), ("D", "12 metros", False)],
            "explicacion": "Perímetro = 2 × (largo + ancho) = 2 × (6 + 4) = 20 metros.",
        },
        {
            "enunciado": "¿Cuál es el área de un cuadrado cuyo lado mide 5 cm?",
            "opciones": [("A", "20 cm²", False), ("B", "25 cm²", True), ("C", "10 cm²", False), ("D", "15 cm²", False)],
            "explicacion": "Área del cuadrado = lado × lado = 5 × 5 = 25 cm².",
        },
        {
            "enunciado": "Un lápiz mide 18 cm. ¿Cuántos milímetros mide?",
            "opciones": [("A", "180 mm", True), ("B", "18 mm", False), ("C", "1.800 mm", False), ("D", "1,8 mm", False)],
            "explicacion": "1 cm equivale a 10 mm, así que 18 cm = 180 mm.",
        },
        {
            "enunciado": "Un rectángulo mide 8 cm de largo y 3 cm de ancho. ¿Cuál es su área?",
            "opciones": [("A", "11 cm²", False), ("B", "22 cm²", False), ("C", "24 cm²", True), ("D", "16 cm²", False)],
            "explicacion": "Área del rectángulo = largo × ancho = 8 × 3 = 24 cm².",
        },
    ],
    ('3', 6): [  # Gráficas estadísticas
        {
            "enunciado": "En una gráfica de barras se muestran las frutas favoritas de un curso: manzana 8 votos, banano 5 votos, uva 10 votos, pera 3 votos. ¿Cuál fruta tuvo más votos?",
            "opciones": [("A", "Manzana", False), ("B", "Banano", False), ("C", "Uva", True), ("D", "Pera", False)],
            "explicacion": "La uva tuvo 10 votos, la barra más alta de todas.",
        },
        {
            "enunciado": "Con los datos anteriores (manzana 8, banano 5, uva 10, pera 3), ¿cuántos estudiantes en total votaron?",
            "opciones": [("A", "26", True), ("B", "23", False), ("C", "28", False), ("D", "18", False)],
            "explicacion": "8 + 5 + 10 + 3 = 26 estudiantes.",
        },
        {
            "enunciado": "Si un pictograma muestra que cada dibujo de manzana representa 2 estudiantes, y hay 4 dibujos de manzanas, ¿cuántos estudiantes representan?",
            "opciones": [("A", "4", False), ("B", "6", False), ("C", "8", True), ("D", "2", False)],
            "explicacion": "4 dibujos × 2 estudiantes cada uno = 8 estudiantes.",
        },
        {
            "enunciado": "Las calificaciones de 5 estudiantes en una prueba fueron: 8, 6, 7, 9, 10. ¿Cuál es el promedio?",
            "opciones": [("A", "7", False), ("B", "8", True), ("C", "9", False), ("D", "6", False)],
            "explicacion": "(8+6+7+9+10) ÷ 5 = 40 ÷ 5 = 8.",
        },
        {
            "enunciado": "En una gráfica de barras sobre mascotas: perros 12, gatos 7, peces 4. ¿Cuántas mascotas más tienen perros que gatos?",
            "opciones": [("A", "3", False), ("B", "5", True), ("C", "8", False), ("D", "19", False)],
            "explicacion": "12 − 7 = 5 mascotas más.",
        },
    ],
    ('4', 1): [  # Números naturales hasta 999.999
        {
            "enunciado": "¿Cómo se escribe con cifras el número trescientos cuarenta y dos mil seiscientos?",
            "opciones": [("A", "342.600", True), ("B", "324.600", False), ("C", "342.060", False), ("D", "34.2600", False)],
            "explicacion": "Trescientos cuarenta y dos mil = 342.000, más seiscientos = 342.600.",
        },
        {
            "enunciado": "En el número 758.394, ¿qué cifra ocupa el lugar de las centenas de mil?",
            "opciones": [("A", "7", True), ("B", "5", False), ("C", "8", False), ("D", "3", False)],
            "explicacion": "El 7 está en la posición de las centenas de mil.",
        },
        {
            "enunciado": "Redondea el número 47.382 a la centena más cercana.",
            "opciones": [("A", "47.300", False), ("B", "47.400", True), ("C", "47.000", False), ("D", "48.000", False)],
            "explicacion": "Las últimas dos cifras (82) son mayores que 50, así que se redondea hacia arriba: 47.400.",
        },
        {
            "enunciado": "¿Cuál propiedad de la suma se aplica en 25 + 18 = 18 + 25?",
            "opciones": [("A", "Asociativa", False), ("B", "Conmutativa", True), ("C", "Distributiva", False), ("D", "Identidad", False)],
            "explicacion": "La propiedad conmutativa dice que el orden de los sumandos no altera la suma.",
        },
        {
            "enunciado": "Ordena de menor a mayor: 128.450, 128.045, 128.540, 128.504. ¿Cuál es el menor?",
            "opciones": [("A", "128.450", False), ("B", "128.045", True), ("C", "128.540", False), ("D", "128.504", False)],
            "explicacion": "128.045 tiene el menor valor en la posición de las centenas entre las cuatro opciones.",
        },
    ],
    ('4', 2): [  # Multiplicación y división
        {
            "enunciado": "Multiplica: 234 × 12.",
            "opciones": [("A", "2.808", True), ("B", "2.708", False), ("C", "2.908", False), ("D", "2.688", False)],
            "explicacion": "234 × 12 = 234 × 10 + 234 × 2 = 2.340 + 468 = 2.808.",
        },
        {
            "enunciado": "Una fábrica produce 156 juguetes por día. ¿Cuántos juguetes produce en 24 días?",
            "opciones": [("A", "3.744", True), ("B", "3.644", False), ("C", "3.844", False), ("D", "3.474", False)],
            "explicacion": "156 × 24 = 156 × 20 + 156 × 4 = 3.120 + 624 = 3.744.",
        },
        {
            "enunciado": "Divide 936 entre 12.",
            "opciones": [("A", "76", False), ("B", "78", True), ("C", "82", False), ("D", "74", False)],
            "explicacion": "12 × 78 = 936.",
        },
        {
            "enunciado": "Al dividir 145 entre 6, ¿cuál es el residuo?",
            "opciones": [("A", "1", True), ("B", "0", False), ("C", "2", False), ("D", "6", False)],
            "explicacion": "6 × 24 = 144, y 145 − 144 = 1 de residuo.",
        },
        {
            "enunciado": "Un vivero tiene 312 plantas y las quiere empacar en cajas de 8 plantas cada una. ¿Cuántas cajas completas puede armar?",
            "opciones": [("A", "38", False), ("B", "39", True), ("C", "40", False), ("D", "36", False)],
            "explicacion": "312 ÷ 8 = 39 cajas exactas.",
        },
    ],
    ('4', 3): [  # Fracciones parte-todo / operador
        {
            "enunciado": "En un salón de 30 estudiantes, 1/3 son niñas. ¿Cuántas niñas hay?",
            "opciones": [("A", "10", True), ("B", "15", False), ("C", "3", False), ("D", "9", False)],
            "explicacion": "30 ÷ 3 = 10 niñas.",
        },
        {
            "enunciado": "¿Cuál fracción es mayor: 2/3 o 3/4?",
            "opciones": [("A", "2/3", False), ("B", "3/4", True), ("C", "Son iguales", False), ("D", "No se puede comparar", False)],
            "explicacion": "2/3 ≈ 0,67 y 3/4 = 0,75, así que 3/4 es mayor.",
        },
        {
            "enunciado": "Un listón mide 60 cm. Si se corta 1/4 del listón, ¿cuántos centímetros se cortaron?",
            "opciones": [("A", "12 cm", False), ("B", "15 cm", True), ("C", "20 cm", False), ("D", "10 cm", False)],
            "explicacion": "60 ÷ 4 = 15 cm.",
        },
        {
            "enunciado": "¿Qué fracción representa la parte sombreada si un círculo se divide en 5 partes iguales y 2 están sombreadas?",
            "opciones": [("A", "2/5", True), ("B", "5/2", False), ("C", "3/5", False), ("D", "2/3", False)],
            "explicacion": "2 partes sombreadas de un total de 5: 2/5.",
        },
        {
            "enunciado": "Compara: 1/2 y 4/8. ¿Qué relación tienen?",
            "opciones": [("A", "1/2 es mayor", False), ("B", "4/8 es mayor", False), ("C", "Son equivalentes", True), ("D", "No se pueden comparar", False)],
            "explicacion": "4/8 se simplifica dividiendo entre 4: 4/8 = 1/2. Son la misma cantidad.",
        },
    ],
    ('4', 4): [  # Ángulos, figuras planas, área/perímetro
        {
            "enunciado": "Un ángulo que mide 130° se clasifica como:",
            "opciones": [("A", "Agudo", False), ("B", "Recto", False), ("C", "Obtuso", True), ("D", "Llano", False)],
            "explicacion": "Un ángulo mayor de 90° y menor de 180° es obtuso.",
        },
        {
            "enunciado": "¿Cuántos lados tiene un cuadrilátero?",
            "opciones": [("A", "3", False), ("B", "4", True), ("C", "5", False), ("D", "6", False)],
            "explicacion": "El prefijo 'cuadri' indica cuatro lados.",
        },
        {
            "enunciado": "Calcula el área de un triángulo con base 10 cm y altura 6 cm.",
            "opciones": [("A", "60 cm²", False), ("B", "30 cm²", True), ("C", "16 cm²", False), ("D", "20 cm²", False)],
            "explicacion": "Área del triángulo = (base × altura) ÷ 2 = (10 × 6) ÷ 2 = 30 cm².",
        },
        {
            "enunciado": "Un paralelogramo tiene base 8 cm y altura 5 cm. ¿Cuál es su área?",
            "opciones": [("A", "13 cm²", False), ("B", "40 cm²", True), ("C", "26 cm²", False), ("D", "20 cm²", False)],
            "explicacion": "Área del paralelogramo = base × altura = 8 × 5 = 40 cm².",
        },
        {
            "enunciado": "Si el perímetro de un cuadrado es 36 cm, ¿cuánto mide cada lado?",
            "opciones": [("A", "6 cm", False), ("B", "9 cm", True), ("C", "12 cm", False), ("D", "18 cm", False)],
            "explicacion": "El cuadrado tiene 4 lados iguales: 36 ÷ 4 = 9 cm cada uno.",
        },
    ],
    ('4', 5): [  # Sistemas de medida
        {
            "enunciado": "¿Cuántos metros hay en 3 kilómetros?",
            "opciones": [("A", "300", False), ("B", "3.000", True), ("C", "30.000", False), ("D", "3", False)],
            "explicacion": "1 km equivale a 1.000 m, así que 3 km = 3.000 m.",
        },
        {
            "enunciado": "Un recipiente contiene 2 litros y medio de agua. ¿Cuántos mililitros son?",
            "opciones": [("A", "250 mL", False), ("B", "2.500 mL", True), ("C", "25.000 mL", False), ("D", "2.050 mL", False)],
            "explicacion": "1 litro equivale a 1.000 mL, así que 2,5 L = 2.500 mL.",
        },
        {
            "enunciado": "Una caja pesa 3 kg y 500 g. ¿Cuántos gramos pesa en total?",
            "opciones": [("A", "3.500 g", True), ("B", "3.050 g", False), ("C", "350 g", False), ("D", "35.000 g", False)],
            "explicacion": "3 kg equivalen a 3.000 g, más 500 g = 3.500 g.",
        },
        {
            "enunciado": "Una película comenzó a las 3:15 p. m. y duró 1 hora y 45 minutos. ¿A qué hora terminó?",
            "opciones": [("A", "4:45 p. m.", False), ("B", "5:00 p. m.", True), ("C", "5:15 p. m.", False), ("D", "4:00 p. m.", False)],
            "explicacion": "3:15 p. m. + 1 h 45 min = 5:00 p. m.",
        },
        {
            "enunciado": "¿Cuántos centímetros hay en 4,5 metros?",
            "opciones": [("A", "45 cm", False), ("B", "450 cm", True), ("C", "4.500 cm", False), ("D", "4,5 cm", False)],
            "explicacion": "1 metro equivale a 100 cm, así que 4,5 m = 450 cm.",
        },
    ],
    ('4', 6): [  # Estadística — tablas de frecuencia, moda, promedio
        {
            "enunciado": "En una tabla de frecuencias, el deporte favorito de 20 estudiantes fue: fútbol 9, baloncesto 6, natación 5. ¿Cuál es la moda?",
            "opciones": [("A", "Fútbol", True), ("B", "Baloncesto", False), ("C", "Natación", False), ("D", "No hay moda", False)],
            "explicacion": "La moda es el dato que más se repite: fútbol, con 9 estudiantes.",
        },
        {
            "enunciado": "Con los datos anteriores (fútbol 9, baloncesto 6, natación 5, de 20 estudiantes), ¿qué fracción de los estudiantes prefiere natación?",
            "opciones": [("A", "5/9", False), ("B", "5/20", True), ("C", "5/6", False), ("D", "20/5", False)],
            "explicacion": "5 estudiantes de un total de 20: 5/20.",
        },
        {
            "enunciado": "Las edades de 5 estudiantes son: 8, 9, 10, 11, 12. ¿Cuál es el promedio de edad?",
            "opciones": [("A", "9", False), ("B", "10", True), ("C", "11", False), ("D", "12", False)],
            "explicacion": "(8+9+10+11+12) ÷ 5 = 50 ÷ 5 = 10.",
        },
        {
            "enunciado": "Un pictograma muestra que cada símbolo representa 5 estudiantes. Si hay 6 símbolos junto a 'transporte en bus', ¿cuántos estudiantes usan el bus?",
            "opciones": [("A", "11", False), ("B", "25", False), ("C", "30", True), ("D", "6", False)],
            "explicacion": "6 símbolos × 5 estudiantes cada uno = 30 estudiantes.",
        },
        {
            "enunciado": "En un diagrama circular que representa el total de una clase, si 'lectura' ocupa la mitad del círculo, ¿qué porcentaje representa?",
            "opciones": [("A", "25%", False), ("B", "50%", True), ("C", "75%", False), ("D", "100%", False)],
            "explicacion": "La mitad de un círculo (el 100% del total) equivale al 50%.",
        },
    ],
    ('5', 1): [  # Enteros, fraccionarios y decimales
        {
            "enunciado": "¿Cuál decimal es equivalente a la fracción 3/4?",
            "opciones": [("A", "0,34", False), ("B", "0,75", True), ("C", "3,4", False), ("D", "0,43", False)],
            "explicacion": "3 ÷ 4 = 0,75.",
        },
        {
            "enunciado": "Ordena de menor a mayor: 0,45, 0,4, 0,54, 0,5. ¿Cuál es el menor?",
            "opciones": [("A", "0,45", False), ("B", "0,4", True), ("C", "0,54", False), ("D", "0,5", False)],
            "explicacion": "0,4 es el menor de los cuatro decimales.",
        },
        {
            "enunciado": "En una tarde muy fría, la temperatura bajó de 3 °C a −2 °C. ¿Cuántos grados bajó la temperatura?",
            "opciones": [("A", "1 °C", False), ("B", "5 °C", True), ("C", "−5 °C", False), ("D", "2 °C", False)],
            "explicacion": "De 3 °C a −2 °C hay una diferencia de 5 grados (3 − (−2) = 5).",
        },
        {
            "enunciado": "¿Cuál es el resultado de convertir 7/10 a decimal?",
            "opciones": [("A", "7,10", False), ("B", "0,7", True), ("C", "0,07", False), ("D", "1,7", False)],
            "explicacion": "7 ÷ 10 = 0,7.",
        },
        {
            "enunciado": "Compara: −3 y −7. ¿Cuál número es mayor?",
            "opciones": [("A", "−3", True), ("B", "−7", False), ("C", "Son iguales", False), ("D", "No se pueden comparar", False)],
            "explicacion": "En los negativos, entre más cerca de cero, mayor es el número: −3 es mayor que −7.",
        },
    ],
    ('5', 2): [  # Operaciones con fracciones y decimales
        {
            "enunciado": "Suma: 1/4 + 1/2. ¿Cuál es el resultado?",
            "opciones": [("A", "2/6", False), ("B", "3/4", True), ("C", "1/6", False), ("D", "2/4", False)],
            "explicacion": "1/2 equivale a 2/4, así que 1/4 + 2/4 = 3/4.",
        },
        {
            "enunciado": "Resta: 3/5 − 1/10.",
            "opciones": [("A", "2/5", False), ("B", "1/2", True), ("C", "7/10", False), ("D", "4/10", False)],
            "explicacion": "3/5 equivale a 6/10, así que 6/10 − 1/10 = 5/10, que simplificado es 1/2.",
        },
        {
            "enunciado": "Multiplica: 2,5 × 4.",
            "opciones": [("A", "8", False), ("B", "10", True), ("C", "12", False), ("D", "6,5", False)],
            "explicacion": "2,5 × 4 = 10.",
        },
        {
            "enunciado": "Un sastre tiene 3,5 metros de tela y usa 1,25 metros para hacer una camisa. ¿Cuántos metros de tela le quedan?",
            "opciones": [("A", "2,25 m", True), ("B", "2,5 m", False), ("C", "1,75 m", False), ("D", "4,75 m", False)],
            "explicacion": "3,5 − 1,25 = 2,25 metros.",
        },
        {
            "enunciado": "Divide: 1/2 ÷ 2.",
            "opciones": [("A", "1/4", True), ("B", "1", False), ("C", "1/2", False), ("D", "2", False)],
            "explicacion": "Dividir 1/2 entre 2 equivale a multiplicar 1/2 por 1/2: 1/4.",
        },
    ],
    ('5', 3): [  # Proporcionalidad
        {
            "enunciado": "Si 3 cuadernos cuestan $9.000, ¿cuánto cuestan 5 cuadernos al mismo precio unitario?",
            "opciones": [("A", "$12.000", False), ("B", "$15.000", True), ("C", "$18.000", False), ("D", "$10.000", False)],
            "explicacion": "Cada cuaderno cuesta $9.000 ÷ 3 = $3.000. Cinco cuadernos: 5 × $3.000 = $15.000.",
        },
        {
            "enunciado": "En una receta, por cada 2 tazas de harina se usa 1 taza de azúcar. Si se usan 6 tazas de harina, ¿cuántas tazas de azúcar se necesitan?",
            "opciones": [("A", "2", False), ("B", "3", True), ("C", "4", False), ("D", "6", False)],
            "explicacion": "6 tazas de harina son el triple de 2, así que se necesita el triple de azúcar: 3 tazas.",
        },
        {
            "enunciado": "¿Cuánto es el 25 % de 200?",
            "opciones": [("A", "25", False), ("B", "50", True), ("C", "75", False), ("D", "100", False)],
            "explicacion": "25 % equivale a 1/4: 200 ÷ 4 = 50.",
        },
        {
            "enunciado": "¿Cuánto es el 50 % de 84?",
            "opciones": [("A", "40", False), ("B", "42", True), ("C", "44", False), ("D", "50", False)],
            "explicacion": "50 % equivale a la mitad: 84 ÷ 2 = 42.",
        },
        {
            "enunciado": "Un carro recorre 240 km en 4 horas a velocidad constante. ¿Cuántos km recorre en 1 hora?",
            "opciones": [("A", "40 km", False), ("B", "60 km", True), ("C", "80 km", False), ("D", "50 km", False)],
            "explicacion": "240 km ÷ 4 horas = 60 km por hora.",
        },
    ],
    ('5', 4): [  # Figuras planas y sólidos
        {
            "enunciado": "¿Cuántos lados tiene un hexágono?",
            "opciones": [("A", "5", False), ("B", "6", True), ("C", "7", False), ("D", "8", False)],
            "explicacion": "El prefijo 'hexa' significa seis: el hexágono tiene 6 lados.",
        },
        {
            "enunciado": "Un polígono con todos sus lados y ángulos iguales se llama:",
            "opciones": [("A", "Irregular", False), ("B", "Regular", True), ("C", "Convexo", False), ("D", "Cóncavo", False)],
            "explicacion": "Un polígono regular tiene todos sus lados y ángulos iguales.",
        },
        {
            "enunciado": "Calcula el área de un rectángulo de 12 cm de largo y 7 cm de ancho.",
            "opciones": [("A", "19 cm²", False), ("B", "84 cm²", True), ("C", "74 cm²", False), ("D", "96 cm²", False)],
            "explicacion": "Área del rectángulo = largo × ancho = 12 × 7 = 84 cm².",
        },
        {
            "enunciado": "¿Cuántos ejes de simetría tiene un cuadrado?",
            "opciones": [("A", "1", False), ("B", "2", False), ("C", "4", True), ("D", "0", False)],
            "explicacion": "Un cuadrado tiene 4 ejes de simetría: 2 diagonales y 2 que unen los puntos medios de los lados.",
        },
        {
            "enunciado": "Un polígono compuesto está formado por un rectángulo de 6 × 4 cm y un triángulo de base 4 cm y altura 3 cm unido a él. ¿Cuál es el área total?",
            "opciones": [("A", "24 cm²", False), ("B", "30 cm²", True), ("C", "18 cm²", False), ("D", "34 cm²", False)],
            "explicacion": "Área del rectángulo = 6×4 = 24 cm². Área del triángulo = (4×3)÷2 = 6 cm². Total: 24 + 6 = 30 cm².",
        },
    ],
    ('5', 5): [  # Recolección y análisis de datos
        {
            "enunciado": "Se encuestó a 40 estudiantes sobre su color favorito: azul 16, rojo 10, verde 14. ¿Qué fracción prefiere el azul?",
            "opciones": [("A", "16/40", True), ("B", "40/16", False), ("C", "10/40", False), ("D", "14/40", False)],
            "explicacion": "16 estudiantes de un total de 40: 16/40.",
        },
        {
            "enunciado": "Con los datos anteriores (azul 16, rojo 10, verde 14), ¿cuál color tiene la menor frecuencia?",
            "opciones": [("A", "Azul", False), ("B", "Rojo", True), ("C", "Verde", False), ("D", "Ninguno", False)],
            "explicacion": "Rojo tiene 10 votos, el número más bajo de los tres.",
        },
        {
            "enunciado": "Las notas de 7 estudiantes en una prueba fueron: 3, 4, 4, 5, 4, 3, 5. ¿Cuál es la moda?",
            "opciones": [("A", "3", False), ("B", "4", True), ("C", "5", False), ("D", "No hay moda", False)],
            "explicacion": "El 4 aparece 3 veces, más que cualquier otro valor.",
        },
        {
            "enunciado": "Las notas de 5 estudiantes, ya ordenadas, son: 2, 3, 4, 5, 6. ¿Cuál es la mediana?",
            "opciones": [("A", "3", False), ("B", "4", True), ("C", "5", False), ("D", "6", False)],
            "explicacion": "La mediana es el valor central de la lista ordenada: 4.",
        },
        {
            "enunciado": "Si una encuesta muestra que 3 de cada 10 estudiantes prefieren estudiar en la tarde, ¿cuántos estudiantes de un curso de 30 preferirían estudiar en la tarde, según esa proporción?",
            "opciones": [("A", "6", False), ("B", "9", True), ("C", "12", False), ("D", "3", False)],
            "explicacion": "3/10 de 30 = (3 × 30) ÷ 10 = 9 estudiantes.",
        },
    ],
    ('5', 6): [  # Probabilidad
        {
            "enunciado": "Al lanzar un dado de 6 caras, ¿qué tipo de evento es obtener un número entre 1 y 6?",
            "opciones": [("A", "Imposible", False), ("B", "Seguro", True), ("C", "Poco probable", False), ("D", "Probable", False)],
            "explicacion": "Todas las caras del dado están entre 1 y 6, así que siempre ocurre: es un evento seguro.",
        },
        {
            "enunciado": "En una bolsa hay 5 fichas rojas y 5 fichas azules. ¿Qué tan probable es sacar una ficha roja?",
            "opciones": [("A", "Imposible", False), ("B", "Poco probable", False), ("C", "Igual de probable que azul", True), ("D", "Seguro", False)],
            "explicacion": "Hay la misma cantidad de fichas rojas y azules, así que la probabilidad es igual para ambas.",
        },
        {
            "enunciado": "Al lanzar una moneda, ¿cuál es la probabilidad de obtener cara?",
            "opciones": [("A", "1/4", False), ("B", "1/3", False), ("C", "1/2", True), ("D", "1", False)],
            "explicacion": "Una moneda tiene 2 caras posibles, así que la probabilidad de cada una es 1/2.",
        },
        {
            "enunciado": "En una bolsa hay 10 bolas: 7 verdes y 3 amarillas. ¿Qué evento es más probable al sacar una bola?",
            "opciones": [("A", "Sacar una bola verde", True), ("B", "Sacar una bola amarilla", False), ("C", "Son igual de probables", False), ("D", "Ninguno es probable", False)],
            "explicacion": "Hay más bolas verdes (7) que amarillas (3), así que es más probable sacar una verde.",
        },
        {
            "enunciado": "Al lanzar un dado de 6 caras, ¿qué tipo de evento es obtener un 7?",
            "opciones": [("A", "Seguro", False), ("B", "Probable", False), ("C", "Poco probable", False), ("D", "Imposible", True)],
            "explicacion": "Un dado de 6 caras solo tiene números del 1 al 6, así que sacar un 7 es imposible.",
        },
    ],
}


def crear_ejercicios(apps, schema_editor):
    DBAPredefinido = apps.get_model('gestion_academica', 'DBAPredefinido')
    EjercicioMath = apps.get_model('halu_math', 'EjercicioMath')
    OpcionEjercicioMath = apps.get_model('halu_math', 'OpcionEjercicioMath')

    creados = 0
    for (grado, numero), items in EJERCICIOS.items():
        dba = DBAPredefinido.objects.filter(area='matematicas', grado=grado, numero=numero).first()
        if not dba:
            logger.warning(
                "halu_math 0004: DBA matematicas/grado=%s/numero=%s no existe todavía "
                "(¿falta correr 'python manage.py cargar_dba'?) — se omite su siembra.",
                grado, numero,
            )
            continue
        for item in items:
            ejercicio = EjercicioMath.objects.create(
                institucion=None,
                es_publica=True,
                dba=dba,
                nivel_dificultad='BASICO',
                enunciado=item["enunciado"],
                explicacion=item.get("explicacion", ""),
                fuente="Halu Math — banco público",
                activo=True,
                creado_por=None,
            )
            for letra, texto, es_correcta in item["opciones"]:
                OpcionEjercicioMath.objects.create(
                    ejercicio=ejercicio,
                    letra=letra,
                    texto=texto,
                    es_correcta=es_correcta,
                )
            creados += 1
    logger.info("halu_math 0004: %s ejercicios públicos creados.", creados)


def eliminar_ejercicios(apps, schema_editor):
    EjercicioMath = apps.get_model('halu_math', 'EjercicioMath')
    EjercicioMath.objects.filter(es_publica=True, fuente="Halu Math — banco público").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('halu_math', '0003_dominiodba_racha_fluida_actual_and_more'),
        ('gestion_academica', '0038_dba_predefinido'),
    ]

    operations = [
        migrations.RunPython(crear_ejercicios, eliminar_ejercicios),
    ]
