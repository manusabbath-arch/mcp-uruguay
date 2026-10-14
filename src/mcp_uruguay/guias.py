"""Guías para quien consume el servidor: flujos con sus trampas (prompts) y referencias (recursos).

Las herramientas devuelven datos; lo que no devuelven es el orden en que conviene pedirlos ni lo que
hay que desconfiar de cada fuente. Esto lo pone al alcance del cliente MCP sin cargar el contexto:
un prompt es una receta que el usuario elige, un recurso es una página de referencia que el cliente
lee cuando la necesita.

Cada flujo nombra herramientas reales y `tests/test_guias.py` falla si una deja de existir o cambia
de nombre. Las trampas son las que cada módulo declara en su docstring, medidas contra las fuentes
reales; no se agregan acá trampas que no estén medidas.
"""

from __future__ import annotations

from mcp_uruguay import herramientas as h

# --- Trampas por herramienta -----------------------------------------------------------------------
# herramienta -> la trampa que declara (una línea). `tests/test_guias.py` exige una por herramienta.
TRAMPAS: dict[str, str] = {
    "cotizacion": (
        "un fin de semana o feriado no tiene cotización: devuelve null salvo `hacia_atras`, y no salta "
        "más de una semana"
    ),
    "cotizacion_mensual": "el mes en curso es parcial y lo dice",
    "pesos_constantes": "usa la Unidad Indexada promedio del mes; es una decisión de análisis, no una lectura",
    "variacion_real": "con la UI, el mes en curso usa los días publicados",
    "ipc_argentina": "es un índice, no una inflación; la API sigue sirviendo bases discontinuadas",
    "ipca_brasil": "la tabla trae varias variables: una variación leída como índice no da error",
    "combustible_ancap": "es el máximo al público con IVA; el precio ex planta es otro dataset y otro número",
    "ventas_combustible": "la columna Unidad mezcla miles de m3 con toneladas; la ventana tiene huecos",
    "paridad_combustibles": "se compara sin impuestos contra sin impuestos; el GLP no se compara ($/L contra $/kg)",
    "clima": "el día va de 9 a 9; un vacío es nulo, no cero; la fuente se actualiza cada quincena",
    "observaciones_inumet": (
        "la fuente publica en UTC y el día es el local (UTC-3); un día incompleto devuelve "
        "null; la agregación es obligatoria"
    ),
    "nivel_rio": "declara la cobertura; una estación sin lecturas no es un cero",
    "nivel_rio_comparado": (
        "la unidad de la altura la publica el servicio sin declararla y la cifra es viva: cambia entre dos corridas"
    ),
    "estaciones_cercanas": "buscar por el nombre del campo del servicio da lista vacía sin error",
    "geocodificar_direccion": (
        "ante lo que no encuentra devuelve el centro de la localidad, una puerta vecina u "
        "otra calle, sin error: mirar la calidad"
    ),
    "ubicar_punto": "sin srsName=EPSG:4326 la capa llega en metros y ningún punto cae adentro",
    "localidad": "el año sale del nombre del campo; el centro aproximado es el del rectángulo, no un centroide",
    "resultados_electorales": (
        "los observados se escrutan en mesas especiales sin habilitados ni localidad: sumar "
        "solo las comunes deja votos afuera"
    ),
    "compras_estado": (
        "el importe es cantidad por precio unitario; llamados y anulaciones no son compras; un solo "
        "ítem puede dominar el total"
    ),
    "asistencia_parlamentaria": (
        "hay más personas que bancas (suplentes) y no hay identificador de persona: los homónimos se confunden"
    ),
    "leyes": "las filas no son leyes: hay duplicadas y una ley 0",
    "pedidos_de_informes": "las respuestas llegan tarde: se compara la misma cohorte, no el total",
    "proyectos_parlamento": "un proyecto puede aparecer en dos legislaturas: las filas no son proyectos",
    "validar_documento": (
        "Excel convierte el RUT en número y se come el cero inicial; la validez es aritmética, no inscripción"
    ),
    "semana": "el año de la semana ISO puede no ser el del día",
    "recursos_catalogo": "las URLs cambian cuando el organismo resube el archivo",
    "buscar_indicador_social": "los nombres salen del título sin tildes; la copia del catálogo abierto es vieja",
    "indicador_social": "trae filas Total mezcladas, puede venir parcial y los mapas pueden traer un solo año",
    "diagnostico": "es la caché de esta máquina: una fuente que no aparece nunca se pidió",
}


def trampas() -> str:
    """Una página con la trampa de cada herramienta, en el orden en que las declara el servidor."""
    filas = "\n".join(f"- `{nombre}`: {texto}" for nombre, texto in TRAMPAS.items())
    return (
        "# Trampas de cada herramienta\n\n"
        "Lo que cada lector sabe de su fuente y un cliente no ve en el número. Un null es sin dato, nunca cero; "
        "los lectores rechazan en vez de arreglar, y una respuesta sin error no es una respuesta sin trampa.\n\n"
        f"{filas}\n"
    )


def fuentes() -> str:
    """De dónde sale cada dato, tal como lo cita la propia respuesta en su campo `fuente`."""
    constantes = sorted(
        (nombre, valor) for nombre, valor in vars(h).items() if nombre.startswith("FUENTE_") and isinstance(valor, str)
    )
    filas = "\n".join(f"- {valor}" for _, valor in constantes)
    return (
        "# Fuentes\n\n"
        "Cada respuesta trae `fuente` (quién publica) y `bajado` (cuándo se obtuvo la copia usada). "
        "Citá las dos junto con el número.\n\n"
        f"{filas}\n"
    )


def estaciones_inumet() -> str:
    """Las siete estaciones de INUMET que acepta `observaciones_inumet`, con el nombre exacto."""
    from uydatos import inumet

    filas = "\n".join(f"- {nombre}" for nombre in inumet.ESTACIONES)
    return (
        "# Estaciones de INUMET\n\n"
        "`observaciones_inumet` acepta el nombre o una parte (por ejemplo `salto` resuelve a la de Salto). "
        "Si el texto coincide con más de una estación rechaza en vez de elegir.\n\n"
        f"{filas}\n"
    )


MONEDAS_BCU = (
    "# Monedas del BCU\n\n"
    "- `USD`: dólar estadounidense billete.\n"
    "- `UI`: Unidad Indexada, la que se usa para llevar pesos corrientes a pesos constantes.\n"
    "- `ARS`: peso argentino billete.\n"
    "- `BRL`: real brasileño billete.\n\n"
    "Todas se expresan en pesos uruguayos. Un fin de semana o feriado no tiene cotización.\n"
)

# --- Flujos (prompts) ------------------------------------------------------------------------------


def combustible_en_pesos_constantes(producto: str = "GASOIL 50-S", desde: str = "2022-02") -> str:
    """El precio de un combustible en pesos de un mismo mes, contra la paridad de importación."""
    return (
        f"Quiero saber cuánto costó de verdad {producto} desde {desde}, en pesos de un mismo mes, y cómo se ubica "
        "contra lo que costaría importarlo. Seguí este orden y no saltees pasos:\n\n"
        f"1. `combustible_ancap` con producto `{producto}` (sin argumentos lista los productos). Es el precio "
        "máximo al público con IVA, mensual y en pesos corrientes. Un mes sin cotización es un hueco: "
        "no lo interpoles.\n"
        '2. `pesos_constantes` con los montos {"AAAA-MM": precio} de ese paso y como base el último mes con '
        "Unidad Indexada publicada. Elegir la base es una decisión de análisis: decí cuál usaste.\n"
        "3. `variacion_real` entre el primer y el último mes: da la variación nominal, la inflación y la real.\n"
        "4. `paridad_combustibles` para el mismo producto: compara el precio ex planta de ANCAP contra la paridad "
        "de importación, sin impuestos contra sin impuestos. El ex planta NO es el precio al público.\n"
        "5. `ventas_combustible` para el volumen. La columna Unidad mezcla miles de m3 con toneladas y la ventana "
        "tiene huecos: compará promedios mensuales, no totales anuales, porque los años no tienen los mismos meses.\n\n"
        "Citá `fuente` y `bajado` de cada herramienta junto a cada número. Si alguna herramienta rechaza, "
        "contá el motivo: no lo reemplaces con una estimación."
    )


def clima_de_salto(desde: str, hasta: str) -> str:
    """Lluvia y temperatura de Salto en una ventana, desde las dos estaciones públicas disponibles."""
    return (
        f"Quiero la lluvia y la temperatura de Salto entre {desde} y {hasta}.\n\n"
        f"1. `clima` con desde `{desde}` y hasta `{hasta}`: estación de INIA en Salto Grande, serie desde 1970. "
        "Su día va de 9 a 9, un vacío es nulo (no cero) y se actualiza cada quincena: si `dias` viene vacío, la "
        "ventana pedida está más allá del último dato y hay que decirlo.\n"
        "2. `observaciones_inumet` con estación `salto` y agregación explícita: `max` o `min` para temperatura, "
        "`suma` para lluvia. El día es el local (UTC-3) y un día incompleto devuelve null.\n\n"
        "Las dos estaciones no están en el mismo punto ni cortan el día a la misma hora: la lluvia diaria de una "
        "no reproduce la de la otra. Compará acumulados de varios días, no días sueltos, y presentá las dos "
        "series por separado con su `fuente` y su `bajado` en vez de promediarlas."
    )


def el_rio_en_salto(dias: int = 7) -> str:
    """El nivel del río en Salto, comparado con la misma época de años anteriores."""
    return (
        f"¿Cómo está el río en Salto en los últimos {dias} días respecto a la misma época de otros años?\n\n"
        f"1. `nivel_rio_comparado` con estación `Salto` y dias `{dias}`: compara la media de la ventana contra las "
        "mismas fechas de cada año. Los años sin la ventana completa se excluyen y se declaran.\n"
        "2. `nivel_rio` para el detalle por día si hace falta, con su cobertura.\n\n"
        "Dos advertencias: la unidad de la altura la publica el servicio sin declararla, y la cifra es viva (la "
        "media del día en curso cambia entre dos corridas). Para decir si es mucho o poco, comparala contra las "
        "cotas oficiales del puerto que publica el organismo de emergencias, y no afirmes que el agua llega a un "
        "lugar sin conocer la cota del terreno de ese lugar."
    )


def compras_del_estado(anio: int, producto: str) -> str:
    """Cuánto adjudicó el Estado de un producto en un año, sin dejar que un solo ítem engañe."""
    return (
        f"¿Cuánto adjudicó el Estado de «{producto}» en {anio}?\n\n"
        f"1. `compras_estado` con anio `{anio}` y buscar `{producto}`. Cuenta solo adjudicaciones activas; "
        "el importe es cantidad por precio unitario; llamados y anulaciones no son compras.\n"
        "2. Antes de citar un total, mirá `aviso` y `mayores_items`: un solo ítem puede ser la mitad del total "
        "y a veces es un registro imposible (el monto en la cantidad y precio 1). Si domina, decilo y mostrá "
        "el total con y sin ese ítem.\n"
        "3. Las monedas se suman aparte; lo que no se pudo convertir a pesos viene en `sin_convertir` y los ítems sin "
        "moneda en `sin_moneda`: no los descartes en silencio.\n"
        "4. La búsqueda es por texto de la descripción: probá singular y plural y la palabra sin tilde, y "
        "revisá que lo que coincidió sea el producto y no otra cosa con el mismo nombre."
    )


def real_o_nominal(monto_inicial: float, mes_inicial: str, monto_final: float, mes_final: str) -> str:
    """Si un monto subió o bajó descontando la inflación."""
    return (
        f"Un monto pasó de {monto_inicial} en {mes_inicial} a {monto_final} en {mes_final}. ¿Subió o bajó en "
        "términos reales?\n\n"
        f"Usá `variacion_real` con esos cuatro valores y el índice `UI`. Devuelve la variación nominal, la "
        "inflación del período y la variación real: informá las tres. El mes en curso usa solo los días "
        "publicados, y la Unidad Indexada es una elección de deflactor, no la única posible: decilo."
    )


#: nombre del prompt -> (función, título). `servidor.py` los registra.
PROMPTS = {
    "combustible_en_pesos_constantes": (
        combustible_en_pesos_constantes,
        "Un combustible en pesos constantes contra la paridad",
    ),
    "clima_de_salto": (clima_de_salto, "Lluvia y temperatura de Salto desde dos estaciones"),
    "el_rio_en_salto": (el_rio_en_salto, "El río en Salto contra la misma época de otros años"),
    "compras_del_estado": (compras_del_estado, "Lo que el Estado adjudicó de un producto en un año"),
    "real_o_nominal": (real_o_nominal, "Si un monto subió en términos reales"),
}

#: uri -> (función, título, descripción). `servidor.py` los registra.
RECURSOS = {
    "uru://trampas": (
        trampas,
        "Trampas de cada herramienta",
        "Lo que cada lector sabe de su fuente y el número no muestra.",
    ),
    "uru://fuentes": (fuentes, "Fuentes", "Quién publica cada dato, como lo cita el campo `fuente`."),
    "uru://inumet/estaciones": (
        estaciones_inumet,
        "Estaciones de INUMET",
        "Las siete estaciones de `observaciones_inumet`.",
    ),
    "uru://bcu/monedas": (lambda: MONEDAS_BCU, "Monedas del BCU", "Qué es cada moneda que acepta `cotizacion`."),
}
