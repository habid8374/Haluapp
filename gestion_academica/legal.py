# gestion_academica/legal.py
"""
Texto oficial de la Política de Tratamiento de Datos Personales de Halu
(Axentia Technologies), en cumplimiento de la Ley 1581 de 2012 y el Decreto
1377 de 2013.

Cambiar POLITICA_TRATAMIENTO_DATOS_VERSION obliga a todos los usuarios a
re-aceptar la política en su próximo inicio de sesión (ver
proyecto_colegio.middleware.PoliticaDatosMiddleware). El hash se calcula
sobre el texto de este archivo, así que basta con editar el contenido y subir
la versión para que quede un registro verificable de qué se aceptó.
"""
import hashlib

POLITICA_TRATAMIENTO_DATOS_VERSION = "2026.1"

POLITICA_TRATAMIENTO_DATOS_SECCIONES = [
    (
        "Identificación del responsable del tratamiento",
        "Nombre: Habid David Acuña Oquendo, persona natural que ejerce actividad "
        "mercantil bajo el nombre comercial Axentia Technologies.\n"
        "Identificación: Cédula de ciudadanía No. 72.287.192 de Barranquilla — "
        "NIT 72.287.192-1.\n"
        "Matrícula Mercantil: No. 940.276, Cámara de Comercio de Barranquilla.\n"
        "Domicilio: Calle 16 N 10a-19, Sabanalarga, Atlántico — Colombia.\n"
        "Correo electrónico: haluplataformaescolar@gmail.com\n"
        "Teléfonos: 324 686 8538 | 300 661 0750",
    ),
    (
        "Marco normativo",
        "Esta política se fundamenta en el artículo 15 de la Constitución "
        "Política de Colombia, la Ley Estatutaria 1581 de 2012, el Decreto "
        "Reglamentario 1377 de 2013, la Ley 1266 de 2008, la Ley 1098 de 2006 "
        "(Código de la Infancia y la Adolescencia) y la Circular Externa 002 "
        "de 2015 de la Superintendencia de Industria y Comercio (SIC), "
        "relativa al tratamiento de datos personales de niños, niñas y "
        "adolescentes.",
    ),
    (
        "Definiciones",
        "Dato personal: cualquier información vinculada o que pueda asociarse "
        "a una o varias personas naturales determinadas o determinables.\n\n"
        "Dato sensible: dato que afecta la intimidad del titular o cuyo uso "
        "indebido puede generar discriminación (por ejemplo, datos de salud o "
        "biométricos).\n\n"
        "Titular: persona natural cuyos datos personales sean objeto de "
        "tratamiento. Incluye estudiantes, acudientes, docentes, "
        "coordinadores, rectores y demás usuarios de la plataforma.\n\n"
        "Tratamiento: cualquier operación sobre datos personales, tales como "
        "recolección, almacenamiento, uso, circulación o supresión.\n\n"
        "Responsable del Tratamiento: Axentia Technologies, respecto de los "
        "datos propios de la operación de su plataforma; cada institución "
        "educativa cliente actúa como Responsable del Tratamiento de los "
        "datos de sus propios estudiantes, en los términos del respectivo "
        "contrato y su anexo de confidencialidad.\n\n"
        "Encargado del Tratamiento: Axentia Technologies, cuando trata datos "
        "personales de estudiantes por cuenta y bajo instrucción de la "
        "institución educativa contratante.",
    ),
    (
        "Principios aplicables al tratamiento",
        "El tratamiento de datos personales dentro de la plataforma Halu se "
        "rige por los principios de legalidad, finalidad, libertad, veracidad "
        "o calidad, transparencia, acceso y circulación restringida, "
        "seguridad y confidencialidad, establecidos en el artículo 4 de la "
        "Ley 1581 de 2012.",
    ),
    (
        "Datos personales objeto de tratamiento",
        "Datos de identificación: nombres, apellidos, tipo y número de "
        "documento, fecha de nacimiento.\n\n"
        "Datos de contacto: dirección, teléfono, correo electrónico.\n\n"
        "Datos académicos: calificaciones, asistencia, observaciones de "
        "convivencia, planes de ajuste razonable (PIAR), resultados de "
        "simulacros y evaluaciones.\n\n"
        "Datos financieros asociados al pago de matrícula y pensiones (no se "
        "almacenan datos completos de tarjetas de crédito o débito; estos "
        "son procesados directamente por la pasarela de pagos).\n\n"
        "Datos biométricos, únicamente cuando la institución habilite "
        "funcionalidades específicas que los requieran, previa autorización "
        "expresa del titular o su representante legal.\n\n"
        "La plataforma trata datos personales de niños, niñas y adolescentes "
        "exclusivamente para las finalidades educativas y administrativas "
        "propias del servicio contratado por la institución educativa, y "
        "bajo las medidas de protección especial descritas en la sección "
        "«Tratamiento de datos de niños, niñas y adolescentes» de esta "
        "política.",
    ),
    (
        "Finalidades del tratamiento",
        "Prestar el servicio de gestión educativa integral contratado por la "
        "institución (académico, financiero, convivencial y "
        "administrativo).\n\n"
        "Generar boletines, certificados, reportes y demás documentos "
        "propios de la gestión escolar.\n\n"
        "Procesar pagos de matrícula y pensiones a través de la pasarela "
        "habilitada por cada institución.\n\n"
        "Emitir la facturación electrónica correspondiente conforme a la "
        "normativa DIAN.\n\n"
        "Enviar notificaciones y comunicaciones propias de la operación de "
        "la plataforma (citas, alertas académicas, recordatorios de "
        "pago).\n\n"
        "Analizar de forma agregada y anonimizada el uso de la plataforma "
        "con fines de mejora del servicio.\n\n"
        "Los datos personales no serán utilizados para fines distintos a "
        "los aquí descritos, ni serán objeto de venta, arriendo o "
        "explotación comercial con terceros.",
    ),
    (
        "Derechos de los titulares",
        "De conformidad con el artículo 8 de la Ley 1581 de 2012, todo "
        "titular de datos personales tiene derecho a:\n\n"
        "Conocer, actualizar y rectificar sus datos personales.\n\n"
        "Solicitar prueba de la autorización otorgada, salvo cuando "
        "expresamente se exceptúe como requisito para el tratamiento.\n\n"
        "Ser informado, previa solicitud, respecto del uso que se ha dado a "
        "sus datos personales.\n\n"
        "Presentar quejas ante la Superintendencia de Industria y Comercio "
        "por infracciones a la normativa de protección de datos.\n\n"
        "Revocar la autorización y/o solicitar la supresión del dato, "
        "siempre que no exista un deber legal o contractual que impida "
        "eliminarlo.\n\n"
        "Acceder de forma gratuita a sus datos personales que hayan sido "
        "objeto de tratamiento.\n\n"
        "Cuando el titular sea menor de edad, estos derechos serán "
        "ejercidos por sus padres, madres o representantes legales, en los "
        "términos de la Ley 1098 de 2006.",
    ),
    (
        "Procedimiento para ejercer los derechos",
        "Las consultas, reclamos, actualizaciones, rectificaciones o "
        "solicitudes de supresión de datos personales deben dirigirse al "
        "correo electrónico haluplataformaescolar@gmail.com, indicando el "
        "nombre completo del titular, el documento de identidad, una "
        "descripción clara de la solicitud y los documentos que la "
        "soporten.\n\n"
        "Las consultas serán atendidas en un término máximo de diez (10) "
        "días hábiles contados a partir de la fecha de recibo. Cuando no "
        "fuere posible atender la consulta dentro de dicho término, se "
        "informará al interesado los motivos de la demora y la fecha en que "
        "se atenderá, la cual en ningún caso superará los cinco (5) días "
        "hábiles siguientes al vencimiento del primer término.\n\n"
        "Los reclamos serán atendidos en un término máximo de quince (15) "
        "días hábiles contados a partir del día siguiente a la fecha de "
        "recibo. Si no fuere posible atenderlo dentro de dicho término, se "
        "informarán los motivos de la demora, siendo el término máximo de "
        "espera de ocho (8) días hábiles adicionales.\n\n"
        "Cuando el titular sea estudiante de una institución educativa "
        "cliente de Halu, la solicitud podrá tramitarse también a través de "
        "la propia institución, en su calidad de Responsable del "
        "Tratamiento.",
    ),
    (
        "Tratamiento de datos de niños, niñas y adolescentes",
        "El tratamiento de datos personales de menores de edad se realiza "
        "respetando el interés superior del menor y sus derechos "
        "fundamentales, conforme al artículo 44 de la Constitución Política "
        "y la Circular Externa 002 de 2015 de la SIC. En consecuencia:\n\n"
        "La recolección de estos datos requiere la autorización previa, "
        "expresa e informada de los padres, madres o representantes "
        "legales, gestionada por la institución educativa en su calidad de "
        "Responsable del Tratamiento.\n\n"
        "Los datos de menores no se utilizan con fines publicitarios, "
        "comerciales o de perfilamiento distintos a la prestación del "
        "servicio educativo contratado.\n\n"
        "Se aplican medidas de seguridad reforzadas y aislamiento de la "
        "información por institución educativa (arquitectura "
        "multi-tenant).",
    ),
    (
        "Transferencia y transmisión de datos a terceros",
        "Para la prestación del servicio, Axentia Technologies puede "
        "apoyarse en proveedores tecnológicos que actúan como subencargados "
        "del tratamiento, tales como servicios de infraestructura en la "
        "nube, almacenamiento de archivos, correo electrónico "
        "transaccional, pasarela de pagos e inteligencia artificial. Dichos "
        "proveedores solo acceden a la información estrictamente necesaria "
        "para la operación del servicio contratado y están sujetos a "
        "obligaciones de confidencialidad y seguridad equivalentes a las "
        "aquí descritas. No se realizan transferencias internacionales de "
        "datos personales distintas a las necesarias para la operación de "
        "dichos proveedores tecnológicos, en los términos permitidos por la "
        "ley.",
    ),
    (
        "Seguridad de la información",
        "Axentia Technologies implementa medidas técnicas, humanas y "
        "administrativas razonables para proteger los datos personales "
        "contra pérdida, uso indebido, acceso no autorizado, alteración o "
        "divulgación, incluyendo cifrado de la información, control de "
        "acceso basado en roles, autenticación reforzada (2FA y passkeys) y "
        "aislamiento de datos por institución educativa.",
    ),
    (
        "Vigencia",
        "La presente política rige a partir de su publicación y las bases "
        "de datos administradas por Axentia Technologies se conservarán "
        "durante el tiempo necesario para cumplir las finalidades que "
        "justificaron su tratamiento y las obligaciones legales o "
        "contractuales aplicables.",
    ),
    (
        "Modificaciones",
        "Axentia Technologies podrá modificar la presente política en "
        "cualquier momento. Los cambios sustanciales serán comunicados a "
        "los titulares a través de los canales de contacto disponibles o "
        "publicados en los medios habituales de la plataforma, antes de su "
        "entrada en vigencia.",
    ),
]


def texto_plano_completo():
    """Concatena versión + todas las secciones en un único texto plano,
    usado tanto para calcular el hash como fuente de verdad del contenido."""
    partes = [f"Versión {POLITICA_TRATAMIENTO_DATOS_VERSION}"]
    for titulo, contenido in POLITICA_TRATAMIENTO_DATOS_SECCIONES:
        partes.append(f"{titulo}\n{contenido}")
    return "\n\n".join(partes)


def hash_politica_vigente():
    """SHA-256 del texto exacto de la política vigente — sirve como
    evidencia de integridad de lo que el usuario aceptó."""
    return hashlib.sha256(texto_plano_completo().encode("utf-8")).hexdigest()
