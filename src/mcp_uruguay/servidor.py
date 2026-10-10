"""El servidor MCP: registra las herramientas de `herramientas.py` y corre por stdio."""

from __future__ import annotations

import functools
from typing import Any, Callable, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from mcp_uruguay import __version__
from mcp_uruguay import herramientas as h

INSTRUCCIONES = """\
Datos públicos de Uruguay y la región, leídos de la fuente primaria.

Cada respuesta trae `fuente` y `bajado` (cuándo se obtuvo la copia usada): citalos junto con el
número. Los lectores rechazan en vez de arreglar: un error con motivo es preferible a un número
plausible pero falso. Los índices de precios se devuelven como índices, no como inflación.
Un null es "sin dato", nunca cero."""

servidor = MCPServer(name="mcp-uruguay", version=__version__, instructions=INSTRUCCIONES)

EN_RED = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)
LOCAL = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


def herramienta(titulo: str, anotaciones: ToolAnnotations) -> Callable:
    """Registra la función y convierte en `ToolError` (con el motivo visible) los errores esperables.

    Los `ValueError` de los lectores ya son mensajes escritos para quien llama: "respuesta mala del
    BCU", "producto inexistente". Un `OSError` es la fuente que no respondió. Cualquier otra
    excepción es un error de este servidor y el SDK la oculta detrás de un mensaje genérico.
    """

    def decorar(funcion: Callable) -> Callable:
        @functools.wraps(funcion)
        def envuelta(*args: Any, **kwargs: Any) -> Any:
            try:
                return funcion(*args, **kwargs)
            except ValueError as e:
                raise ToolError(str(e)) from e
            except OSError as e:
                raise ToolError(f"No se pudo consultar la fuente: {e}. Probar de nuevo más tarde.") from e

        return servidor.tool(title=titulo, annotations=anotaciones)(envuelta)

    return decorar


@herramienta("Cotización del BCU de un día", EN_RED)
def cotizacion(moneda: Literal["USD", "UI", "ARS", "BRL"], fecha: str, hacia_atras: bool = False) -> h.Cotizacion:
    """Cotización oficial del Banco Central del Uruguay, en pesos uruguayos, para una fecha AAAA-MM-DD.

    Monedas: USD (dólar billete), UI (Unidad Indexada), ARS (peso argentino billete), BRL (real billete).
    Fines de semana y feriados no tienen publicación: con hacia_atras=true se usa el último día hábil
    previo (hasta 7 días) y la respuesta dice qué día se usó."""
    return h.cotizacion(moneda, fecha, hacia_atras)


@herramienta("Promedio mensual de una cotización del BCU", EN_RED)
def cotizacion_mensual(moneda: Literal["USD", "UI", "ARS", "BRL"], desde: str, hasta: str) -> h.CotizacionMensual:
    """Promedio mensual de una cotización del BCU entre dos meses AAAA-MM (hasta 240 meses), con la
    cantidad de días publicados de cada mes. El mes en curso viene marcado como incompleto."""
    return h.cotizacion_mensual(moneda, desde, hasta)


@herramienta("Pesos constantes con la Unidad Indexada", EN_RED)
def pesos_constantes(montos: dict[str, float], base: str) -> h.PesosConstantes:
    """Lleva montos en pesos corrientes de distintos meses a pesos de un mes base, deflactando con la
    Unidad Indexada promedio del BCU. `montos` es {"AAAA-MM": monto}; `base` es "AAAA-MM".
    Sirve para comparar en términos reales pesos de fechas distintas."""
    return h.pesos_constantes(montos, base)


@herramienta("IPC de Argentina (INDEC)", EN_RED)
def ipc_argentina(desde: str, hasta: str) -> h.IpcArgentina:
    """Índice de precios al consumidor nacional de Argentina, base dic-2016 = 100, entre dos meses AAAA-MM.
    Devuelve el índice, no la inflación."""
    return h.ipc_argentina(desde, hasta)


@herramienta("IPCA de Brasil (IBGE)", EN_RED)
def ipca_brasil(desde: str, hasta: str) -> h.IpcaBrasil:
    """IPCA de Brasil como número-índice (base dic-1993 = 100), entre dos meses AAAA-MM.
    Devuelve el índice, no la inflación."""
    return h.ipca_brasil(desde, hasta)


@herramienta("Precios de combustibles de ANCAP", EN_RED)
def combustible_ancap(
    producto: Optional[str] = None, anio: Optional[int] = None, mes: Optional[int] = None
) -> h.CombustibleAncap:
    """Precio máximo al público, con IVA, de los combustibles de ANCAP fijado por el Poder Ejecutivo.
    Sin `producto`, lista los productos disponibles (los nombres hay que pasarlos tal cual).
    Con `producto`, la serie mensual; con `anio` y `mes`, ese mes."""
    return h.combustible_ancap(producto, anio, mes)


@herramienta("Clima en Salto Grande (INIA)", EN_RED)
def clima(desde: str = "", hasta: str = "") -> h.Clima:
    """Clima de la estacion INIA Salto Grande, la misma serie desde 1970.

    Sin fechas: la tendencia de la temperatura media anual, en grados Celsius por decada, con su
    error estandar. Con `desde` y `hasta` (AAAA-MM-DD, hasta 400 dias): la lluvia y las temperaturas
    maxima y minima de cada dia, con la anomalia respecto de la normal 1971-2025. Se pasan las dos
    fechas o ninguna."""
    return h.clima(desde, hasta)


@herramienta("Estaciones hidrometeorológicas cercanas (Salto Grande)", EN_RED)
def estaciones_cercanas(lat: float, lon: float, cantidad: int = 5) -> h.EstacionesCercanas:
    """Estaciones de la red de la Comisión Técnica Mixta de Salto Grande (cuenca del río Uruguay, las dos
    orillas) más cercanas a un punto, con las variables que publica cada una y su último dato."""
    return h.estaciones_cercanas(lat, lon, cantidad)


@herramienta("Validar RUT o cédula uruguaya", LOCAL)
def validar_documento(numero: str, tipo: Literal["rut", "ci"]) -> h.Validacion:
    """Valida el dígito verificador de un RUT (12 dígitos) o una cédula de identidad (8 dígitos) de
    Uruguay. Acepta puntos, guiones y comas. No consulta a DGI: es validez aritmética."""
    return h.validar_documento(numero, tipo)


@herramienta("Semana ISO de una fecha", LOCAL)
def semana(fecha: str) -> h.SemanaTyped:
    """Semana ISO 8601 (W1, W2...) de una fecha AAAA-MM-DD, con su lunes y su domingo."""
    return h.semana(fecha)


@herramienta("Geocodificar una dirección de Uruguay (IDE.uy)", EN_RED)
def geocodificar_direccion(direccion: str, localidad: str = "", departamento: str = "") -> h.Geocodificacion:
    """Coordenadas (lat, lon) de una dirección o esquina de Uruguay con la API oficial de IDE.uy, con la
    calidad del resultado: puerta exacta, puerta aproximada, esquina o centro de calle. Si la API devuelve
    otra calle o el centro de la localidad, no se da coordenada. Pasar localidad y departamento mejora
    mucho el resultado. Esquinas: '18 de Julio y Ejido' o 'Artigas esq. Solari'."""
    return h.geocodificar_direccion(direccion, localidad, departamento)


@herramienta("Recursos de un dataset del catálogo de Uruguay", EN_RED)
def recursos_catalogo(dataset: str) -> h.RecursosCatalogo:
    """Los archivos vigentes (nombre, URL, formato, fecha) de un dataset de catalogodatos.gub.uy, por su
    identificador (por ejemplo `inia-precipitacion-temps-extremas-sg`)."""
    return h.recursos_catalogo(dataset)


@herramienta("Que copia de cada fuente se esta usando", LOCAL)
def diagnostico() -> h.Diagnostico:
    """Que archivo de cada fuente esta cacheado en esta maquina, de cuando es la copia que se esta
    usando, y cuanto pesa. Sirve para saber si un numero viejo viene de una copia vieja.
    No sale a la red."""
    return h.diagnostico()


def main() -> None:
    servidor.run()


if __name__ == "__main__":
    main()
