"""
Seed migration: ~200 ICFES Saber format questions across all grades and areas.
All questions are public (es_publica=True, institucion=None).
"""
from django.db import migrations


PREGUNTAS = [
    # ═══════════════════════════════════════════════
    # LECTURA CRÍTICA — Grado 11
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee el siguiente fragmento: «La ciencia no es una colección de verdades absolutas, sino un proceso continuo de aproximación a la realidad mediante la observación, la hipótesis y la experimentación.» ¿Cuál es la idea principal del texto?",
        "opciones": [
            ("A", "La ciencia produce verdades definitivas", False),
            ("B", "La ciencia es un proceso dinámico de búsqueda del conocimiento", True),
            ("C", "La observación es el único método científico válido", False),
            ("D", "La hipótesis es más importante que la experimentación", False),
        ],
        "explicacion": "El texto describe la ciencia como un proceso continuo, no como una colección de verdades fijas.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "En el enunciado «Los ríos son las venas de la tierra», la expresión en cursiva es un recurso literario llamado:",
        "opciones": [
            ("A", "Hipérbole", False),
            ("B", "Metáfora", True),
            ("C", "Símil", False),
            ("D", "Personificación", False),
        ],
        "explicacion": "Una metáfora establece una identidad directa entre dos elementos sin usar conectores comparativos.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "Un autor afirma: «Las redes sociales son la causa principal del deterioro de las relaciones interpersonales». ¿Qué tipo de falacia argumentativa contiene esta afirmación?",
        "opciones": [
            ("A", "Apelación a la autoridad", False),
            ("B", "Generalización apresurada", True),
            ("C", "Ad hominem", False),
            ("D", "Falsa dicotomía", False),
        ],
        "explicacion": "Atribuir a una sola causa un fenómeno complejo, sin evidencia suficiente, es una generalización apresurada.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuál es la función principal de un párrafo introductorio en un texto expositivo?",
        "opciones": [
            ("A", "Presentar la conclusión del texto", False),
            ("B", "Narrar una historia relacionada con el tema", False),
            ("C", "Presentar el tema y captar la atención del lector", True),
            ("D", "Refutar argumentos contrarios", False),
        ],
        "explicacion": "El párrafo introductorio tiene como función presentar el tema y orientar al lector sobre lo que tratará el texto.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "Un ensayo argumentativo tiene como objetivo principal:",
        "opciones": [
            ("A", "Describir objetivamente los hechos", False),
            ("B", "Contar una historia de forma cronológica", False),
            ("C", "Defender una posición con argumentos sólidos", True),
            ("D", "Explicar un proceso paso a paso", False),
        ],
        "explicacion": "El ensayo argumentativo busca convencer al lector mediante razones y argumentos bien fundamentados.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee: «El sol se despidió lentamente del horizonte, tiñendo el cielo de naranja y rosa.» ¿Qué figura literaria aparece en este fragmento?",
        "opciones": [
            ("A", "Hipérbole", False),
            ("B", "Personificación", True),
            ("C", "Metáfora", False),
            ("D", "Anáfora", False),
        ],
        "explicacion": "La personificación atribuye acciones humanas (despedirse) a seres inanimados (el sol).",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "La intertextualidad en literatura se refiere a:",
        "opciones": [
            ("A", "La relación entre el autor y el lector", False),
            ("B", "Las relaciones que un texto establece con otros textos", True),
            ("C", "El uso de vocabulario técnico en un texto", False),
            ("D", "La estructura narrativa de un cuento", False),
        ],
        "explicacion": "La intertextualidad describe cómo un texto hace referencia, cita o dialoga con otros textos preexistentes.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuál de los siguientes elementos NO pertenece a la estructura de un texto narrativo?",
        "opciones": [
            ("A", "Tesis", True),
            ("B", "Narrador", False),
            ("C", "Personajes", False),
            ("D", "Conflicto", False),
        ],
        "explicacion": "La tesis pertenece al texto argumentativo, no al narrativo. El texto narrativo incluye narrador, personajes y conflicto.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    # ═══════════════════════════════════════════════
    # MATEMÁTICAS — Grado 11
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "Si f(x) = 2x² − 3x + 1, ¿cuál es el valor de f(3)?",
        "opciones": [
            ("A", "8", False),
            ("B", "10", True),
            ("C", "12", False),
            ("D", "6", False),
        ],
        "explicacion": "f(3) = 2(9) − 3(3) + 1 = 18 − 9 + 1 = 10.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "La ecuación de la recta que pasa por los puntos (0, 2) y (3, 8) es:",
        "opciones": [
            ("A", "y = 2x + 2", True),
            ("B", "y = 3x + 2", False),
            ("C", "y = 2x − 2", False),
            ("D", "y = x + 2", False),
        ],
        "explicacion": "Pendiente m = (8−2)/(3−0) = 2. La ecuación es y = 2x + 2.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuántas soluciones reales tiene la ecuación x² + 4x + 5 = 0?",
        "opciones": [
            ("A", "Dos soluciones reales distintas", False),
            ("B", "Una solución real doble", False),
            ("C", "Ninguna solución real", True),
            ("D", "Infinitas soluciones", False),
        ],
        "explicacion": "Discriminante: Δ = 16 − 20 = −4 < 0, por lo tanto no tiene soluciones reales.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Un rectángulo tiene base de 8 cm y altura de 5 cm. ¿Cuál es su área?",
        "opciones": [
            ("A", "26 cm²", False),
            ("B", "40 cm²", True),
            ("C", "13 cm²", False),
            ("D", "80 cm²", False),
        ],
        "explicacion": "Área = base × altura = 8 × 5 = 40 cm².",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "Si log₂(x) = 4, ¿cuál es el valor de x?",
        "opciones": [
            ("A", "8", False),
            ("B", "16", True),
            ("C", "12", False),
            ("D", "4", False),
        ],
        "explicacion": "log₂(x) = 4 significa 2⁴ = x, por lo tanto x = 16.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "En una encuesta a 200 estudiantes, 80 prefieren matemáticas. ¿Qué porcentaje representa esto?",
        "opciones": [
            ("A", "25%", False),
            ("B", "40%", True),
            ("C", "45%", False),
            ("D", "60%", False),
        ],
        "explicacion": "(80/200) × 100 = 40%.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "La derivada de f(x) = x³ − 5x + 2 es:",
        "opciones": [
            ("A", "f'(x) = 3x² − 5", True),
            ("B", "f'(x) = x² − 5", False),
            ("C", "f'(x) = 3x − 5", False),
            ("D", "f'(x) = 3x² + 2", False),
        ],
        "explicacion": "Aplicando la regla de la potencia: d/dx(x³) = 3x², d/dx(−5x) = −5, d/dx(2) = 0.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Si la probabilidad de que llueva mañana es 0,35, ¿cuál es la probabilidad de que NO llueva?",
        "opciones": [
            ("A", "0,35", False),
            ("B", "0,65", True),
            ("C", "0,70", False),
            ("D", "0,30", False),
        ],
        "explicacion": "P(no llueva) = 1 − P(llueva) = 1 − 0,35 = 0,65.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál de las siguientes expresiones es equivalente a sen²(x) + cos²(x)?",
        "opciones": [
            ("A", "0", False),
            ("B", "2", False),
            ("C", "1", True),
            ("D", "sen(x)·cos(x)", False),
        ],
        "explicacion": "La identidad pitagórica fundamental establece que sen²(x) + cos²(x) = 1.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Una progresión aritmética tiene primer término a₁ = 3 y razón común d = 4. ¿Cuál es el décimo término?",
        "opciones": [
            ("A", "37", False),
            ("B", "39", True),
            ("C", "43", False),
            ("D", "35", False),
        ],
        "explicacion": "aₙ = a₁ + (n−1)d = 3 + (10−1)×4 = 3 + 36 = 39.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    # ═══════════════════════════════════════════════
    # CIENCIAS NATURALES — Grado 11
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuál es la función principal del ADN en las células?",
        "opciones": [
            ("A", "Producir energía para la célula", False),
            ("B", "Almacenar y transmitir la información genética", True),
            ("C", "Sintetizar proteínas directamente", False),
            ("D", "Regular el pH celular", False),
        ],
        "explicacion": "El ADN contiene la información genética que se transmite de generación en generación y dirige la síntesis de proteínas mediante el ARN.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Indagación científica",
        "enunciado": "La Segunda Ley de la Termodinámica establece que:",
        "opciones": [
            ("A", "La energía se crea a partir de la materia", False),
            ("B", "La entropía de un sistema aislado tiende a aumentar", True),
            ("C", "La energía se puede transformar perfectamente sin pérdidas", False),
            ("D", "La temperatura siempre aumenta en los procesos naturales", False),
        ],
        "explicacion": "La Segunda Ley establece que la entropía (desorden) de un sistema aislado tiende a aumentar o permanecer constante.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿En cuál de las siguientes opciones se representa correctamente la fotosíntesis?",
        "opciones": [
            ("A", "CO₂ + O₂ → glucosa + H₂O", False),
            ("B", "glucosa + O₂ → CO₂ + H₂O + energía", False),
            ("C", "CO₂ + H₂O + luz → glucosa + O₂", True),
            ("D", "H₂O + O₂ → glucosa + CO₂", False),
        ],
        "explicacion": "En la fotosíntesis, las plantas usan CO₂, H₂O y energía lumínica para producir glucosa y liberar O₂.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "ALTO",
        "competencia": "Explicación de fenómenos",
        "enunciado": "En la tabla periódica, los elementos del grupo 1 (metales alcalinos) tienen en común:",
        "opciones": [
            ("A", "Tener 2 electrones en el último nivel de energía", False),
            ("B", "Ser metales de transición", False),
            ("C", "Tener 1 electrón en el último nivel de energía", True),
            ("D", "Ser gases nobles", False),
        ],
        "explicacion": "Los metales alcalinos tienen un solo electrón en su capa de valencia, lo que los hace muy reactivos.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "La velocidad de la luz en el vacío es aproximadamente:",
        "opciones": [
            ("A", "3 × 10⁶ m/s", False),
            ("B", "3 × 10⁸ m/s", True),
            ("C", "3 × 10¹⁰ m/s", False),
            ("D", "3 × 10⁴ m/s", False),
        ],
        "explicacion": "La velocidad de la luz en el vacío es aproximadamente 3 × 10⁸ metros por segundo (300.000 km/s).",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Indagación científica",
        "enunciado": "¿Qué tipo de enlace químico se forma cuando dos átomos comparten electrones?",
        "opciones": [
            ("A", "Enlace iónico", False),
            ("B", "Enlace covalente", True),
            ("C", "Enlace metálico", False),
            ("D", "Enlace de hidrógeno", False),
        ],
        "explicacion": "En el enlace covalente, dos átomos comparten uno o más pares de electrones para completar su octeto.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "ALTO",
        "competencia": "Explicación de fenómenos",
        "enunciado": "La meiosis produce células con:",
        "opciones": [
            ("A", "El mismo número de cromosomas que la célula madre", False),
            ("B", "El doble de cromosomas que la célula madre", False),
            ("C", "La mitad de cromosomas que la célula madre", True),
            ("D", "Cromosomas dañados", False),
        ],
        "explicacion": "La meiosis es una división celular reductora que produce gametos con la mitad del número de cromosomas (haploide).",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "La Ley de Gravitación Universal establece que la fuerza gravitacional entre dos cuerpos es:",
        "opciones": [
            ("A", "Proporcional a la suma de sus masas e inversamente proporcional a la distancia", False),
            ("B", "Proporcional al producto de sus masas e inversamente proporcional al cuadrado de la distancia", True),
            ("C", "Independiente de las masas de los cuerpos", False),
            ("D", "Proporcional a la distancia entre los cuerpos", False),
        ],
        "explicacion": "F = G(m₁·m₂)/r², donde G es la constante gravitacional, m las masas y r la distancia.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    # ═══════════════════════════════════════════════
    # SOCIALES Y CIUDADANAS — Grado 11
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Conocimiento histórico",
        "enunciado": "¿En qué año Colombia promulgó su Constitución Política vigente?",
        "opciones": [
            ("A", "1886", False),
            ("B", "1991", True),
            ("C", "1948", False),
            ("D", "2000", False),
        ],
        "explicacion": "La Constitución Política de Colombia fue promulgada el 4 de julio de 1991 por la Asamblea Nacional Constituyente.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Cuál es la principal función de la rama legislativa del poder público en Colombia?",
        "opciones": [
            ("A", "Administrar justicia", False),
            ("B", "Ejecutar las leyes", False),
            ("C", "Hacer las leyes y controlar políticamente al gobierno", True),
            ("D", "Defender los derechos de los ciudadanos", False),
        ],
        "explicacion": "El Congreso de la República (rama legislativa) tiene como función principal elaborar las leyes y ejercer control político sobre el ejecutivo.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Conocimiento histórico",
        "enunciado": "La Revolución Industrial inició principalmente en:",
        "opciones": [
            ("A", "Francia", False),
            ("B", "Estados Unidos", False),
            ("C", "Gran Bretaña", True),
            ("D", "Alemania", False),
        ],
        "explicacion": "La Primera Revolución Industrial comenzó en Gran Bretaña a mediados del siglo XVIII, gracias a la máquina de vapor y la industria textil.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "El concepto de «Estado social de derecho» en Colombia implica:",
        "opciones": [
            ("A", "Que el Estado solo debe garantizar el orden público", False),
            ("B", "Que el Estado debe garantizar los derechos fundamentales y el bienestar social de todos los ciudadanos", True),
            ("C", "Que los ciudadanos no tienen obligaciones con el Estado", False),
            ("D", "Que el Estado puede ignorar la Constitución en emergencias", False),
        ],
        "explicacion": "El artículo 1° de la Constitución define Colombia como un Estado social de derecho, comprometido con la dignidad humana y el bienestar colectivo.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Interpretación y análisis de perspectivas",
        "enunciado": "¿Cuál fue el principal impacto de la Segunda Guerra Mundial en el orden político mundial?",
        "opciones": [
            ("A", "La creación de la Unión Europea", False),
            ("B", "La configuración de un mundo bipolar (EE.UU. vs URSS)", True),
            ("C", "El fin del capitalismo", False),
            ("D", "La unificación de Alemania", False),
        ],
        "explicacion": "Tras la Segunda Guerra Mundial surgió la Guerra Fría, un enfrentamiento ideológico y geopolítico entre EE.UU. (capitalismo) y la URSS (comunismo).",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Conocimiento histórico",
        "enunciado": "El proceso de independencia de Colombia se consolidó en la Batalla de:",
        "opciones": [
            ("A", "Calibío", False),
            ("B", "Boyacá", True),
            ("C", "Pichincha", False),
            ("D", "Junín", False),
        ],
        "explicacion": "La Batalla de Boyacá, el 7 de agosto de 1819, fue el enfrentamiento decisivo que consolidó la independencia de la Nueva Granada.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Cuál de los siguientes derechos es un derecho fundamental en Colombia?",
        "opciones": [
            ("A", "Derecho al trabajo", False),
            ("B", "Derecho a la vida", True),
            ("C", "Derecho a una vivienda digna", False),
            ("D", "Derecho a la educación", False),
        ],
        "explicacion": "El derecho a la vida (Art. 11 Constitución) es un derecho fundamental inviolable. Los otros son derechos económicos, sociales y culturales.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    # ═══════════════════════════════════════════════
    # INGLÉS — Grado 11
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión lectora en inglés",
        "enunciado": "Choose the correct answer. She _____ to the store yesterday.",
        "opciones": [
            ("A", "go", False),
            ("B", "goes", False),
            ("C", "went", True),
            ("D", "going", False),
        ],
        "explicacion": "'Yesterday' indicates past tense. The simple past of 'go' is 'went'.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión lectora en inglés",
        "enunciado": "What does the word 'beautiful' mean in Spanish?",
        "opciones": [
            ("A", "feo", False),
            ("B", "pequeño", False),
            ("C", "hermoso/a", True),
            ("D", "rápido", False),
        ],
        "explicacion": "'Beautiful' means 'hermoso/a' or 'bello/a' in Spanish.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "MEDIO",
        "competencia": "Producción escrita en inglés",
        "enunciado": "Which sentence is grammatically correct?",
        "opciones": [
            ("A", "I have never been to Paris", True),
            ("B", "I have never went to Paris", False),
            ("C", "I never have been to Paris", False),
            ("D", "I have been never to Paris", False),
        ],
        "explicacion": "With the present perfect, the correct form uses the past participle 'been', and 'never' goes between the auxiliary and the main verb.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "ALTO",
        "competencia": "Comprensión lectora en inglés",
        "enunciado": "Read: 'Despite the heavy rain, the match continued.' What does 'despite' express?",
        "opciones": [
            ("A", "Cause", False),
            ("B", "Result", False),
            ("C", "Concession / contrast", True),
            ("D", "Addition", False),
        ],
        "explicacion": "'Despite' (a pesar de) expresses concession — something happened even though a contrasting condition existed.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión lectora en inglés",
        "enunciado": "The sentence 'If I had studied harder, I would have passed the exam' is in the:",
        "opciones": [
            ("A", "First conditional (real present)", False),
            ("B", "Second conditional (unreal present)", False),
            ("C", "Third conditional (unreal past)", True),
            ("D", "Zero conditional (general truth)", False),
        ],
        "explicacion": "The third conditional uses 'if + past perfect, would + have + past participle' to describe unreal situations in the past.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    # ═══════════════════════════════════════════════
    # LECTURA CRÍTICA — Grado 9
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_9", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuál es la diferencia principal entre un texto narrativo y un texto descriptivo?",
        "opciones": [
            ("A", "El narrativo usa imágenes y el descriptivo usa palabras", False),
            ("B", "El narrativo cuenta hechos en secuencia y el descriptivo detalla características", True),
            ("C", "El narrativo es más corto que el descriptivo", False),
            ("D", "El descriptivo siempre usa rima y el narrativo no", False),
        ],
        "explicacion": "El texto narrativo presenta acciones en orden temporal, mientras el descriptivo pinta con palabras características de personas, objetos o lugares.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee el fragmento: «El camino era largo, pero ella no se rindió. Cada paso la acercaba más a su sueño.» ¿Qué emoción transmite el texto?",
        "opciones": [
            ("A", "Tristeza y resignación", False),
            ("B", "Perseverancia y esperanza", True),
            ("C", "Miedo y desesperación", False),
            ("D", "Indiferencia y calma", False),
        ],
        "explicacion": "Las palabras 'no se rindió' y 'acercaba a su sueño' transmiten determinación y esperanza.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "¿Cuál de las siguientes opciones es un argumento de autoridad?",
        "opciones": [
            ("A", "«Todos mis amigos piensan que es así, por lo tanto debe ser correcto»", False),
            ("B", "«Según estudios de la Universidad Nacional, el 70% de los colombianos lee menos de un libro al año»", True),
            ("C", "«Si no haces ejercicio, vas a enfermarte y morirás pronto»", False),
            ("D", "«Tienes razón porque eres muy inteligente»", False),
        ],
        "explicacion": "El argumento de autoridad cita fuentes reconocidas (instituciones, expertos) para respaldar una afirmación.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    # ═══════════════════════════════════════════════
    # MATEMÁTICAS — Grado 9
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "¿Cuál es el máximo común divisor (MCD) de 24 y 36?",
        "opciones": [
            ("A", "6", False),
            ("B", "12", True),
            ("C", "24", False),
            ("D", "4", False),
        ],
        "explicacion": "Los divisores de 24: 1,2,3,4,6,8,12,24. Los de 36: 1,2,3,4,6,9,12,18,36. El mayor común es 12.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "Si 3x − 7 = 14, ¿cuál es el valor de x?",
        "opciones": [
            ("A", "5", False),
            ("B", "7", True),
            ("C", "3", False),
            ("D", "9", False),
        ],
        "explicacion": "3x = 14 + 7 = 21, entonces x = 21/3 = 7.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "El perímetro de un cuadrado es 36 cm. ¿Cuánto mide cada lado?",
        "opciones": [
            ("A", "6 cm", False),
            ("B", "9 cm", True),
            ("C", "12 cm", False),
            ("D", "4 cm", False),
        ],
        "explicacion": "Perímetro = 4 × lado. Entonces lado = 36/4 = 9 cm.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es la pendiente de la recta que pasa por A(1, 3) y B(4, 9)?",
        "opciones": [
            ("A", "1", False),
            ("B", "2", True),
            ("C", "3", False),
            ("D", "1/2", False),
        ],
        "explicacion": "m = (y₂−y₁)/(x₂−x₁) = (9−3)/(4−1) = 6/3 = 2.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "¿Cuánto es 2³ × 2²?",
        "opciones": [
            ("A", "2⁶", False),
            ("B", "2⁵", True),
            ("C", "4⁵", False),
            ("D", "2¹", False),
        ],
        "explicacion": "Al multiplicar potencias de igual base, se suman los exponentes: 2³ × 2² = 2^(3+2) = 2⁵.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    # ═══════════════════════════════════════════════
    # CIENCIAS NATURALES — Grado 9
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_9", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuál es la diferencia entre una mezcla homogénea y una mezcla heterogénea?",
        "opciones": [
            ("A", "En la homogénea se pueden separar los componentes fácilmente", False),
            ("B", "En la homogénea la composición es uniforme en toda la muestra", True),
            ("C", "En la heterogénea todos los componentes tienen el mismo aspecto", False),
            ("D", "No hay diferencia, son lo mismo", False),
        ],
        "explicacion": "En una mezcla homogénea (solución), la composición es uniforme. En una heterogénea, se pueden distinguir los componentes.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuál es el proceso por el cual las plantas fabrican su propio alimento?",
        "opciones": [
            ("A", "Respiración celular", False),
            ("B", "Fotosíntesis", True),
            ("C", "Fermentación", False),
            ("D", "Digestión", False),
        ],
        "explicacion": "La fotosíntesis es el proceso mediante el cual las plantas convierten la energía lumínica en energía química (glucosa).",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "ALTO",
        "competencia": "Indagación científica",
        "enunciado": "Si aumentas la presión sobre un gas a temperatura constante, el volumen:",
        "opciones": [
            ("A", "Aumenta proporcionalmente", False),
            ("B", "Se mantiene igual", False),
            ("C", "Disminuye inversamente", True),
            ("D", "Se duplica", False),
        ],
        "explicacion": "Según la Ley de Boyle: a temperatura constante, P × V = constante. Si P aumenta, V disminuye inversamente.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué tipo de energía tiene un cuerpo en movimiento?",
        "opciones": [
            ("A", "Energía potencial gravitacional", False),
            ("B", "Energía cinética", True),
            ("C", "Energía química", False),
            ("D", "Energía nuclear", False),
        ],
        "explicacion": "La energía cinética es la energía asociada al movimiento: Ec = ½mv².",
        "fuente": "Simulacro ICFES Saber 9",
    },
    # ═══════════════════════════════════════════════
    # SOCIALES — Grado 9
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_9", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Conocimiento histórico",
        "enunciado": "¿Cuándo fue la declaración de independencia de Colombia (primera)?",
        "opciones": [
            ("A", "20 de julio de 1810", True),
            ("B", "7 de agosto de 1819", False),
            ("C", "4 de julio de 1776", False),
            ("D", "5 de noviembre de 1811", False),
        ],
        "explicacion": "El 20 de julio de 1810 se llevó a cabo el grito de independencia en Bogotá, fecha que se celebra como el día nacional.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Qué es el PIB (Producto Interno Bruto)?",
        "opciones": [
            ("A", "El total de exportaciones de un país", False),
            ("B", "El valor total de bienes y servicios producidos en un país en un período", True),
            ("C", "La deuda externa de un país", False),
            ("D", "El ingreso promedio por habitante", False),
        ],
        "explicacion": "El PIB es el valor monetario total de la producción de bienes y servicios de un país en un período determinado (generalmente un año).",
        "fuente": "Simulacro ICFES Saber 9",
    },
    # ═══════════════════════════════════════════════
    # MATEMÁTICAS — Grado 7
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "¿Cuánto es -5 + 8?",
        "opciones": [
            ("A", "-3", False),
            ("B", "3", True),
            ("C", "13", False),
            ("D", "-13", False),
        ],
        "explicacion": "-5 + 8 = 3. Se suma el valor absoluto mayor (8) menos el menor (5) y se toma el signo del mayor.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es el resultado de (−3) × (−4)?",
        "opciones": [
            ("A", "-12", False),
            ("B", "12", True),
            ("C", "7", False),
            ("D", "-7", False),
        ],
        "explicacion": "El producto de dos números negativos es positivo: (−3) × (−4) = +12.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "¿Cuánto es 3/4 + 1/2?",
        "opciones": [
            ("A", "4/6", False),
            ("B", "5/4", True),
            ("C", "4/8", False),
            ("D", "1/4", False),
        ],
        "explicacion": "1/2 = 2/4. Entonces 3/4 + 2/4 = 5/4.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Un triángulo tiene ángulos de 60° y 80°. ¿Cuánto mide el tercer ángulo?",
        "opciones": [
            ("A", "30°", False),
            ("B", "40°", True),
            ("C", "50°", False),
            ("D", "20°", False),
        ],
        "explicacion": "La suma de ángulos de un triángulo es 180°. Tercer ángulo = 180° − 60° − 80° = 40°.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es el valor de la expresión 4² − 2³ + 5?",
        "opciones": [
            ("A", "11", False),
            ("B", "13", True),
            ("C", "9", False),
            ("D", "7", False),
        ],
        "explicacion": "4² = 16, 2³ = 8. Entonces: 16 − 8 + 5 = 13.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    # ═══════════════════════════════════════════════
    # LECTURA CRÍTICA — Grado 7
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_7", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuál es la diferencia entre sinónimo y antónimo?",
        "opciones": [
            ("A", "Los sinónimos tienen el mismo significado y los antónimos el opuesto", True),
            ("B", "Los antónimos tienen el mismo significado y los sinónimos el opuesto", False),
            ("C", "Son lo mismo, solo cambia la pronunciación", False),
            ("D", "Los sinónimos son palabras extranjeras", False),
        ],
        "explicacion": "Sinónimo: palabra con igual o similar significado. Antónimo: palabra con significado opuesto.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee: «Pedro come tanto que parece un elefante.» ¿Qué figura literaria se usa?",
        "opciones": [
            ("A", "Metáfora", False),
            ("B", "Símil", True),
            ("C", "Personificación", False),
            ("D", "Hipérbole", False),
        ],
        "explicacion": "El símil (o comparación) establece semejanza entre dos elementos usando conectores como 'parece', 'como', 'igual que'.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    # ═══════════════════════════════════════════════
    # CIENCIAS NATURALES — Grado 7
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_7", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuáles son los tres estados de la materia?",
        "opciones": [
            ("A", "Líquido, vapor y plasma", False),
            ("B", "Sólido, líquido y gaseoso", True),
            ("C", "Frío, caliente y tibio", False),
            ("D", "Orgánico, inorgánico y mixto", False),
        ],
        "explicacion": "Los tres estados clásicos de la materia son: sólido (forma y volumen fijos), líquido (volumen fijo, forma variable) y gaseoso (forma y volumen variables).",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué organelo celular es conocido como la «central energética» de la célula?",
        "opciones": [
            ("A", "Núcleo", False),
            ("B", "Ribosoma", False),
            ("C", "Mitocondria", True),
            ("D", "Vacuola", False),
        ],
        "explicacion": "La mitocondria produce la mayor parte del ATP (energía) que la célula necesita mediante la respiración celular.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "ALTO",
        "competencia": "Indagación científica",
        "enunciado": "¿Cuál es la fórmula química del agua?",
        "opciones": [
            ("A", "H₂O₂", False),
            ("B", "HO₂", False),
            ("C", "H₂O", True),
            ("D", "H₃O", False),
        ],
        "explicacion": "El agua está formada por dos átomos de hidrógeno y uno de oxígeno: H₂O.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    # ═══════════════════════════════════════════════
    # SOCIALES — Grado 7
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_7", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Conocimiento histórico",
        "enunciado": "¿Cuál es la capital de Colombia?",
        "opciones": [
            ("A", "Medellín", False),
            ("B", "Cali", False),
            ("C", "Bogotá", True),
            ("D", "Barranquilla", False),
        ],
        "explicacion": "Bogotá D.C. (Distrito Capital) es la capital y ciudad más poblada de Colombia.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Cuáles son los tres poderes del Estado colombiano?",
        "opciones": [
            ("A", "Ejecutivo, Legislativo y Policial", False),
            ("B", "Ejecutivo, Legislativo y Judicial", True),
            ("C", "Presidencial, Congresional y Constitucional", False),
            ("D", "Central, Regional y Local", False),
        ],
        "explicacion": "La separación de poderes (Montesquieu) se refleja en el Estado colombiano: Ejecutivo (Presidente), Legislativo (Congreso) y Judicial (Cortes).",
        "fuente": "Simulacro ICFES Saber 7",
    },
    # ═══════════════════════════════════════════════
    # MATEMÁTICAS — Grado 5
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "María tiene 24 canicas y quiere repartirlas en 4 grupos iguales. ¿Cuántas canicas tendrá cada grupo?",
        "opciones": [
            ("A", "4", False),
            ("B", "6", True),
            ("C", "8", False),
            ("D", "5", False),
        ],
        "explicacion": "24 ÷ 4 = 6 canicas por grupo.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "¿Cuánto es 356 + 247?",
        "opciones": [
            ("A", "593", False),
            ("B", "603", True),
            ("C", "613", False),
            ("D", "583", False),
        ],
        "explicacion": "356 + 247: unidades: 6+7=13 (escribo 3, llevo 1), decenas: 5+4+1=10 (escribo 0, llevo 1), centenas: 3+2+1=6. Resultado: 603.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál de las siguientes fracciones es equivalente a 2/3?",
        "opciones": [
            ("A", "3/4", False),
            ("B", "4/6", True),
            ("C", "2/4", False),
            ("D", "6/8", False),
        ],
        "explicacion": "2/3 × 2/2 = 4/6. Las fracciones equivalentes se obtienen multiplicando o dividiendo numerador y denominador por el mismo número.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "En una tienda hay 5 cajas con 12 lápices cada una. ¿Cuántos lápices hay en total?",
        "opciones": [
            ("A", "17", False),
            ("B", "50", False),
            ("C", "60", True),
            ("D", "52", False),
        ],
        "explicacion": "5 × 12 = 60 lápices en total.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuánto es 1/4 de 80?",
        "opciones": [
            ("A", "16", False),
            ("B", "20", True),
            ("C", "25", False),
            ("D", "40", False),
        ],
        "explicacion": "1/4 de 80 = 80 ÷ 4 = 20.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    # ═══════════════════════════════════════════════
    # LECTURA CRÍTICA — Grado 5
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_5", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee: «El zorro astuto engañó al cuervo para robarle el queso.» ¿Qué tipo de texto es este?",
        "opciones": [
            ("A", "Texto informativo", False),
            ("B", "Texto narrativo (fábula)", True),
            ("C", "Texto instructivo", False),
            ("D", "Texto argumentativo", False),
        ],
        "explicacion": "Es un texto narrativo — cuenta una historia con personajes animales que tienen características humanas (fábula).",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuál es la palabra que mejor describe a alguien «valiente»?",
        "opciones": [
            ("A", "Cobarde", False),
            ("B", "Temeroso", False),
            ("C", "Audaz", True),
            ("D", "Perezoso", False),
        ],
        "explicacion": "Audaz es sinónimo de valiente: alguien que actúa con valentía y atrevimiento.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    # ═══════════════════════════════════════════════
    # CIENCIAS NATURALES — Grado 5
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_5", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuántos planetas tiene nuestro sistema solar?",
        "opciones": [
            ("A", "7", False),
            ("B", "8", True),
            ("C", "9", False),
            ("D", "10", False),
        ],
        "explicacion": "El Sistema Solar tiene 8 planetas: Mercurio, Venus, Tierra, Marte, Júpiter, Saturno, Urano y Neptuno. Plutón fue reclasificado en 2006.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué órgano del cuerpo humano bombea la sangre?",
        "opciones": [
            ("A", "El pulmón", False),
            ("B", "El hígado", False),
            ("C", "El corazón", True),
            ("D", "El riñón", False),
        ],
        "explicacion": "El corazón es el órgano principal del sistema circulatorio. Bombea la sangre hacia todo el cuerpo.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué animales son mamíferos?",
        "opciones": [
            ("A", "Serpiente, lagartija y cocodrilo", False),
            ("B", "Perro, ballena y murciélago", True),
            ("C", "Paloma, pingüino y loro", False),
            ("D", "Rana, sapo y salamandra", False),
        ],
        "explicacion": "Los mamíferos se caracterizan por tener pelo o pelaje y amamantar a sus crías. El perro, la ballena y el murciélago son mamíferos.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    # ═══════════════════════════════════════════════
    # SOCIALES — Grado 5
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_5", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Conocimiento histórico",
        "enunciado": "¿Cuántos departamentos tiene Colombia?",
        "opciones": [
            ("A", "24", False),
            ("B", "28", False),
            ("C", "32", True),
            ("D", "36", False),
        ],
        "explicacion": "Colombia está dividida en 32 departamentos y el Distrito Capital de Bogotá.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Cuál es la función principal del alcalde en un municipio?",
        "opciones": [
            ("A", "Hacer las leyes del municipio", False),
            ("B", "Dirigir y administrar el gobierno local", True),
            ("C", "Juzgar a los ciudadanos", False),
            ("D", "Recaudar impuestos nacionales", False),
        ],
        "explicacion": "El alcalde es el jefe del ejecutivo municipal, responsable de la administración y gobierno del municipio.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    # ═══════════════════════════════════════════════
    # MATEMÁTICAS — Grado 3
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Juan tiene 15 manzanas y le da 6 a su hermano. ¿Cuántas manzanas le quedan?",
        "opciones": [
            ("A", "7", False),
            ("B", "9", True),
            ("C", "11", False),
            ("D", "8", False),
        ],
        "explicacion": "15 − 6 = 9 manzanas.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Comunicación, representación y modelación",
        "enunciado": "¿Cuánto es 7 × 8?",
        "opciones": [
            ("A", "54", False),
            ("B", "56", True),
            ("C", "48", False),
            ("D", "63", False),
        ],
        "explicacion": "7 × 8 = 56. Tabla del 7: 7, 14, 21, 28, 35, 42, 49, 56.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es el número que continúa en la secuencia: 2, 4, 6, 8, ___?",
        "opciones": [
            ("A", "9", False),
            ("B", "10", True),
            ("C", "11", False),
            ("D", "12", False),
        ],
        "explicacion": "La secuencia son los números pares, se suma 2 cada vez: 8 + 2 = 10.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "BASICO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Si hay 3 filas con 5 sillas cada una, ¿cuántas sillas hay en total?",
        "opciones": [
            ("A", "8", False),
            ("B", "12", False),
            ("C", "15", True),
            ("D", "20", False),
        ],
        "explicacion": "3 × 5 = 15 sillas.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál figura tiene 4 lados iguales y 4 ángulos rectos?",
        "opciones": [
            ("A", "Triángulo", False),
            ("B", "Rectángulo", False),
            ("C", "Cuadrado", True),
            ("D", "Círculo", False),
        ],
        "explicacion": "El cuadrado tiene 4 lados iguales y 4 ángulos de 90°.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    # ═══════════════════════════════════════════════
    # LECTURA CRÍTICA — Grado 3
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_3", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee: «El gato maullaba muy fuerte porque tenía mucha hambre.» ¿Por qué maullaba el gato?",
        "opciones": [
            ("A", "Porque estaba asustado", False),
            ("B", "Porque tenía hambre", True),
            ("C", "Porque quería dormir", False),
            ("D", "Porque estaba enfermo", False),
        ],
        "explicacion": "El texto dice claramente: el gato maullaba porque tenía hambre.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "LECTURA_CRITICA", "nivel_dificultad": "BASICO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "¿Cuántas sílabas tiene la palabra «mariposa»?",
        "opciones": [
            ("A", "3", False),
            ("B", "4", True),
            ("C", "5", False),
            ("D", "2", False),
        ],
        "explicacion": "ma-ri-po-sa = 4 sílabas.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "LECTURA_CRITICA", "nivel_dificultad": "MEDIO",
        "competencia": "Comprensión e interpretación textual",
        "enunciado": "Lee: «La abeja vuela de flor en flor recogiendo néctar para hacer la miel.» ¿Qué hace la abeja con el néctar?",
        "opciones": [
            ("A", "Lo guarda en su colmena para alimentar a la reina", False),
            ("B", "Lo usa para hacer la miel", True),
            ("C", "Lo comparte con las mariposas", False),
            ("D", "Lo bota al suelo", False),
        ],
        "explicacion": "El texto dice claramente que recoge el néctar 'para hacer la miel'.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    # ═══════════════════════════════════════════════
    # CIENCIAS NATURALES — Grado 3
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_3", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Cuál de los siguientes seres vivos es una planta?",
        "opciones": [
            ("A", "Perro", False),
            ("B", "Orquídea", True),
            ("C", "Pez", False),
            ("D", "Hormiga", False),
        ],
        "explicacion": "La orquídea es una planta con flores. Los otros son animales.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "BASICO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué necesitan las plantas para crecer?",
        "opciones": [
            ("A", "Solo agua", False),
            ("B", "Agua, luz solar y minerales del suelo", True),
            ("C", "Solo luz solar", False),
            ("D", "Carne y agua", False),
        ],
        "explicacion": "Las plantas necesitan agua, luz solar y nutrientes del suelo para realizar la fotosíntesis y crecer.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    # ═══════════════════════════════════════════════
    # EXTRA — Más preguntas Grado 11 para completar
    # ═══════════════════════════════════════════════
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es el valor de sen(30°)?",
        "opciones": [
            ("A", "√3/2", False),
            ("B", "1/2", True),
            ("C", "√2/2", False),
            ("D", "1", False),
        ],
        "explicacion": "sen(30°) = 1/2. Valores notables: sen(30°)=1/2, sen(45°)=√2/2, sen(60°)=√3/2, sen(90°)=1.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "¿Cuántos números enteros hay entre -3 y 4 (sin incluirlos)?",
        "opciones": [
            ("A", "5", False),
            ("B", "6", True),
            ("C", "7", False),
            ("D", "4", False),
        ],
        "explicacion": "Los enteros son: -2, -1, 0, 1, 2, 3 → 6 números.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "ALTO",
        "competencia": "Explicación de fenómenos",
        "enunciado": "En la ecuación química: 2H₂ + O₂ → 2H₂O, ¿cuántas moléculas de H₂ se necesitan para producir 4 moléculas de agua?",
        "opciones": [
            ("A", "2", False),
            ("B", "4", True),
            ("C", "6", False),
            ("D", "8", False),
        ],
        "explicacion": "La razón es 2H₂:2H₂O = 1:1. Para producir 4H₂O se necesitan 4H₂.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "ALTO",
        "competencia": "Interpretación y análisis de perspectivas",
        "enunciado": "¿Cuál fue el papel del Plan Marshall en la posguerra?",
        "opciones": [
            ("A", "Invadir militarmente a los países derrotados", False),
            ("B", "Financiar la reconstrucción económica de Europa occidental", True),
            ("C", "Crear la ONU para mantener la paz", False),
            ("D", "Juzgar a los criminales de guerra nazis", False),
        ],
        "explicacion": "El Plan Marshall (1948) fue un programa de ayuda económica estadounidense para reconstruir Europa occidental después de la Segunda Guerra Mundial.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "ALTO",
        "competencia": "Comprensión lectora en inglés",
        "enunciado": "Read: 'The more you practice, the better you get.' This sentence expresses:",
        "opciones": [
            ("A", "A hypothetical situation", False),
            ("B", "A proportional relationship", True),
            ("C", "A past habit", False),
            ("D", "A future prediction", False),
        ],
        "explicacion": "The 'the more... the better' structure expresses a proportional relationship between two variables.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "INGLES", "nivel_dificultad": "MEDIO",
        "competencia": "Producción escrita en inglés",
        "enunciado": "Choose the correct passive voice: 'Someone built this house in 1990.'",
        "opciones": [
            ("A", "This house is built in 1990", False),
            ("B", "This house was built in 1990", True),
            ("C", "This house has been built in 1990", False),
            ("D", "This house had built in 1990", False),
        ],
        "explicacion": "For past simple passive, use: was/were + past participle. 'Built' is the past participle of 'build'.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_9", "area": "LECTURA_CRITICA", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "¿Cuál es la diferencia entre un hecho y una opinión en un texto?",
        "opciones": [
            ("A", "El hecho es subjetivo y la opinión es objetiva", False),
            ("B", "El hecho es verificable y la opinión es una valoración personal", True),
            ("C", "El hecho siempre usa comillas y la opinión no", False),
            ("D", "No hay diferencia entre hecho y opinión", False),
        ],
        "explicacion": "Un hecho puede ser comprobado objetivamente. Una opinión expresa la valoración o punto de vista de una persona.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "Si el radio de un círculo es 7 cm, ¿cuál es su área aproximada? (π ≈ 3,14)",
        "opciones": [
            ("A", "43,98 cm²", False),
            ("B", "153,86 cm²", True),
            ("C", "21,98 cm²", False),
            ("D", "78,5 cm²", False),
        ],
        "explicacion": "A = π × r² = 3,14 × 7² = 3,14 × 49 = 153,86 cm².",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué tipo de onda es el sonido?",
        "opciones": [
            ("A", "Onda transversal que no necesita medio de propagación", False),
            ("B", "Onda longitudinal que necesita un medio para propagarse", True),
            ("C", "Onda electromagnética que viaja en el vacío", False),
            ("D", "Onda transversal que viaja solo en el agua", False),
        ],
        "explicacion": "El sonido es una onda mecánica longitudinal (las partículas oscilan en la dirección de propagación) que requiere un medio material.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_9", "area": "SOCIALES", "nivel_dificultad": "ALTO",
        "competencia": "Interpretación y análisis de perspectivas",
        "enunciado": "El proceso de globalización económica ha tenido como consecuencia:",
        "opciones": [
            ("A", "El aislamiento económico de los países", False),
            ("B", "Mayor interdependencia económica entre los países", True),
            ("C", "La desaparición del comercio internacional", False),
            ("D", "La eliminación de las empresas multinacionales", False),
        ],
        "explicacion": "La globalización ha incrementado la interconexión económica entre naciones, generando tanto oportunidades como desigualdades.",
        "fuente": "Simulacro ICFES Saber 9",
    },
    {
        "grado_nivel": "GRADO_7", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Formulación y resolución de problemas",
        "enunciado": "Si x + 5 = 12, ¿cuánto vale x?",
        "opciones": [
            ("A", "5", False),
            ("B", "7", True),
            ("C", "17", False),
            ("D", "6", False),
        ],
        "explicacion": "x = 12 − 5 = 7.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "¿Qué tipo de nutrición tienen los hongos?",
        "opciones": [
            ("A", "Autótrofa (fabrican su propio alimento)", False),
            ("B", "Heterótrofa saprofítica (se alimentan de materia orgánica en descomposición)", True),
            ("C", "Fotosintética como las plantas", False),
            ("D", "Carnívora, como algunos insectos", False),
        ],
        "explicacion": "Los hongos son organismos heterótrofos saprofitos: obtienen nutrientes descomponiendo materia orgánica muerta.",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_7", "area": "LECTURA_CRITICA", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "Lee: «Hay que cuidar el agua porque es un recurso no renovable.» ¿Cuál es el argumento del texto?",
        "opciones": [
            ("A", "El agua no existe en la naturaleza", False),
            ("B", "Debemos cuidar el agua porque se puede agotar", True),
            ("C", "El agua es infinita", False),
            ("D", "No es necesario cuidar el agua", False),
        ],
        "explicacion": "El argumento es: cuidar el agua es necesario porque es un recurso que puede agotarse (no renovable).",
        "fuente": "Simulacro ICFES Saber 7",
    },
    {
        "grado_nivel": "GRADO_5", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es la figura geométrica que tiene 3 lados?",
        "opciones": [
            ("A", "Cuadrado", False),
            ("B", "Triángulo", True),
            ("C", "Pentágono", False),
            ("D", "Hexágono", False),
        ],
        "explicacion": "El triángulo es el polígono con 3 lados y 3 ángulos.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_5", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Conocimiento histórico",
        "enunciado": "¿Cuál es el río más largo de Colombia?",
        "opciones": [
            ("A", "Río Cauca", False),
            ("B", "Río Magdalena", True),
            ("C", "Río Putumayo", False),
            ("D", "Río Meta", False),
        ],
        "explicacion": "El río Magdalena, con aproximadamente 1.528 km, es el río más importante y largo de Colombia.",
        "fuente": "Simulacro ICFES Saber 5",
    },
    {
        "grado_nivel": "GRADO_3", "area": "MATEMATICAS", "nivel_dificultad": "MEDIO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "¿Cuál es el número mayor: 427, 472, 274 o 247?",
        "opciones": [
            ("A", "427", False),
            ("B", "472", True),
            ("C", "274", False),
            ("D", "247", False),
        ],
        "explicacion": "Se comparan las centenas: todos tienen 4 o 2 centenas. 4 > 2, entonces descartamos 274 y 247. Entre 427 y 472: las decenas 7 > 2, entonces 472 > 427.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Uso del conocimiento científico",
        "enunciado": "El ciclo del agua incluye los siguientes procesos:",
        "opciones": [
            ("A", "Evaporación, condensación y precipitación", True),
            ("B", "Fotosíntesis, respiración y descomposición", False),
            ("C", "Germinación, crecimiento y floración", False),
            ("D", "Calentamiento, enfriamiento y fusión solamente", False),
        ],
        "explicacion": "El ciclo del agua se compone principalmente de: evaporación (agua → vapor), condensación (vapor → nubes) y precipitación (lluvia/nieve).",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_3", "area": "SOCIALES", "nivel_dificultad": "BASICO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Qué hace un médico?",
        "opciones": [
            ("A", "Construye edificios", False),
            ("B", "Cuida la salud de las personas", True),
            ("C", "Vende alimentos", False),
            ("D", "Enseña en el colegio", False),
        ],
        "explicacion": "El médico es el profesional de la salud que diagnostica enfermedades y cuida el bienestar de las personas.",
        "fuente": "Simulacro ICFES Saber 3",
    },
    {
        "grado_nivel": "GRADO_11", "area": "LECTURA_CRITICA", "nivel_dificultad": "ALTO",
        "competencia": "Pensamiento crítico y argumentación",
        "enunciado": "Según la teoría de la comunicación, el «ruido» en un proceso comunicativo se refiere a:",
        "opciones": [
            ("A", "El volumen del sonido emitido", False),
            ("B", "Cualquier interferencia que distorsiona el mensaje", True),
            ("C", "El receptor del mensaje", False),
            ("D", "El canal de comunicación", False),
        ],
        "explicacion": "El ruido comunicativo es cualquier elemento (físico, semántico o psicológico) que interfiere y distorsiona la transmisión correcta del mensaje.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "MATEMATICAS", "nivel_dificultad": "ALTO",
        "competencia": "Razonamiento y argumentación",
        "enunciado": "Si A y B son eventos independientes con P(A)=0,4 y P(B)=0,5, ¿cuál es P(A∩B)?",
        "opciones": [
            ("A", "0,9", False),
            ("B", "0,2", True),
            ("C", "0,45", False),
            ("D", "0,1", False),
        ],
        "explicacion": "Para eventos independientes: P(A∩B) = P(A) × P(B) = 0,4 × 0,5 = 0,2.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "CIENCIAS_NATURALES", "nivel_dificultad": "MEDIO",
        "competencia": "Explicación de fenómenos",
        "enunciado": "¿Cuál es la diferencia entre mitosis y meiosis?",
        "opciones": [
            ("A", "La mitosis produce 4 células y la meiosis produce 2", False),
            ("B", "La mitosis produce células diploides idénticas y la meiosis produce células haploides genéticamente variadas", True),
            ("C", "Solo la meiosis ocurre en células animales", False),
            ("D", "La mitosis reduce el número de cromosomas a la mitad", False),
        ],
        "explicacion": "La mitosis produce 2 células diploides (2n) idénticas para crecimiento/reparación. La meiosis produce 4 células haploides (n) para reproducción sexual.",
        "fuente": "Simulacro ICFES Saber 11",
    },
    {
        "grado_nivel": "GRADO_11", "area": "SOCIALES", "nivel_dificultad": "MEDIO",
        "competencia": "Pensamiento sistémico",
        "enunciado": "¿Qué mecanismo de participación ciudadana permite a los ciudadanos revocar el mandato de un gobernante elegido?",
        "opciones": [
            ("A", "Referendo", False),
            ("B", "Consulta popular", False),
            ("C", "Revocatoria del mandato", True),
            ("D", "Iniciativa legislativa popular", False),
        ],
        "explicacion": "La revocatoria del mandato (Art. 103 Constitución) permite a los ciudadanos retirar a un gobernante antes de terminar su período.",
        "fuente": "Simulacro ICFES Saber 11",
    },
]


def crear_preguntas(apps, schema_editor):
    BancoPregunta = apps.get_model('simulacros', 'BancoPregunta')
    OpcionPregunta = apps.get_model('simulacros', 'OpcionPregunta')

    for data in PREGUNTAS:
        pregunta = BancoPregunta.objects.create(
            grado_nivel=data["grado_nivel"],
            area=data["area"],
            nivel_dificultad=data["nivel_dificultad"],
            competencia=data.get("competencia", ""),
            componente=data.get("componente", ""),
            enunciado=data["enunciado"],
            explicacion=data.get("explicacion", ""),
            fuente=data.get("fuente", "Simulacro ICFES"),
            es_publica=True,
            institucion=None,
            creado_por=None,
        )
        for letra, texto, es_correcta in data["opciones"]:
            OpcionPregunta.objects.create(
                pregunta=pregunta,
                letra=letra,
                texto=texto,
                es_correcta=es_correcta,
            )


def eliminar_preguntas(apps, schema_editor):
    BancoPregunta = apps.get_model('simulacros', 'BancoPregunta')
    BancoPregunta.objects.filter(es_publica=True, fuente__icontains='ICFES').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simulacros', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_preguntas, eliminar_preguntas),
    ]
