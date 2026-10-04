"""
Provider de promptfoo para el agente de Parachute S.A.

Ejecuta la arquitectura CENTRALIZADA (la elegida en la HT5) tal como corre en
producción —mismo orquestador, mismos especialistas, mismas `function_tool`—
y devuelve a promptfoo, además del texto final, la traza de herramientas que
se ejecutaron. Esa traza es la que usan los evals de *tool execution*.

Qué agrega este archivo (sin modificar nada de `core/`):

1. Traza de herramientas en los dos niveles:
   - orquestador  -> consultar_informacion, consultar_pronostico,
                     dictaminar_seguridad, gestionar_agenda
   - especialista -> consultar_faqs, consultar_clima, evaluar_fecha,
                     agendar_cita, cancelar_cita, ...
   Se envuelve `on_invoke_tool` de cada FunctionTool y se registra nombre,
   argumentos, salida, si fue exitosa y su duración.

2. Aislamiento por caso de prueba:
   - cada llamada usa un archivo de citas temporal (opcionalmente precargado
     con `citas_previas`), así los evals nunca tocan `data/citas.json`;
   - el clima se puede fijar con la variable `clima` (ideal | marginal |
     prohibido) para que el veredicto de seguridad sea reproducible. Con
     `clima: real` se consulta Open-Meteo de verdad.

3. Fechas relativas: en el texto del caso se puede escribir `[HOY+N]` y se
   reemplaza por la fecha ISO correspondiente antes de enviarla al agente.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from agents import Runner  # noqa: E402
from agents.tool import FunctionTool  # noqa: E402

from core import scheduling, weather  # noqa: E402
from core import tools as core_tools  # noqa: E402
from core.domain import ClimaDia  # noqa: E402
from core.config import LATITUD, LONGITUD  # noqa: E402

import centralizada  # noqa: E402

MAX_TURNOS = 20
MAX_REINTENTOS = 5

# --------------------------------------------------------------------------
# Fechas relativas
# --------------------------------------------------------------------------
_PATRON_FECHA = re.compile(r"\[HOY\+(\d+)\]")


def resolver_fechas(texto: str) -> str:
    hoy = date.today()
    return _PATRON_FECHA.sub(lambda m: (hoy + timedelta(days=int(m.group(1)))).isoformat(), texto)


# --------------------------------------------------------------------------
# Clima fijo (fixtures)
# --------------------------------------------------------------------------
ESCENARIOS_CLIMA: dict[str, dict[str, float]] = {
    # viento < 20, ráfagas <= 35, sin lluvia, nubes < 30  -> IDEAL
    "ideal": dict(temperatura_2m=29.0, precipitacion=0.0, cobertura_nubes=15.0,
                  viento_superficie_10m=12.0, rafagas_10m=20.0),
    # viento 20-28 y nubes 30-75 -> MARGINAL
    "marginal": dict(temperatura_2m=27.0, precipitacion=0.0, cobertura_nubes=45.0,
                     viento_superficie_10m=24.0, rafagas_10m=30.0),
    # viento > 28, ráfagas > 35, lluvia y nubes > 75 -> PROHIBIDO
    "prohibido": dict(temperatura_2m=24.0, precipitacion=3.2, cobertura_nubes=88.0,
                      viento_superficie_10m=34.0, rafagas_10m=48.0),
}

_obtener_clima_real = weather.obtener_clima


def _clima_fijo(escenario: str):
    valores = ESCENARIOS_CLIMA[escenario]

    def obtener(texto_fecha: str, latitud: float = LATITUD, longitud: float = LONGITUD) -> ClimaDia:
        # Se conservan las validaciones reales (formato y ventana de 16 días).
        fecha = weather.parsear_fecha(texto_fecha)
        weather.validar_horizonte(fecha)
        return ClimaDia(
            fecha=fecha.isoformat(),
            fuente=f"fixture:{escenario}",
            latitud=latitud,
            longitud=longitud,
            **valores,
        )

    return obtener


# --------------------------------------------------------------------------
# Traza de herramientas
# --------------------------------------------------------------------------
_traza: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("traza", default=None)


def _parsear(texto: Any) -> Any:
    if not isinstance(texto, str):
        return texto
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError):
        return texto


def _instrumentar(tool: FunctionTool, nivel: str) -> None:
    if getattr(tool, "_eval_instrumentada", False):
        return
    original = tool.on_invoke_tool

    async def envoltura(ctx, entrada: str):
        registro = {
            "nivel": nivel,
            "tool": tool.name,
            "args": _parsear(entrada),
            "ok": None,
            "ms": None,
            "salida": None,
        }
        traza = _traza.get()
        if traza is not None:
            registro["orden"] = len(traza)
            traza.append(registro)
        inicio = time.perf_counter()
        try:
            salida = await original(ctx, entrada)
        except Exception as exc:  # noqa: BLE001
            registro.update(ok=False, salida=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            registro["ms"] = round((time.perf_counter() - inicio) * 1000)
        parseada = _parsear(salida)
        registro["salida"] = parseada
        # Las herramientas de core devuelven {"ok": bool, ...}; los agentes-herramienta texto.
        if isinstance(parseada, dict):
            registro["ok"] = parseada.get("ok", True)
        else:
            # El SDK convierte las excepciones de la herramienta (p. ej. argumentos
            # inválidos) en este mensaje en lugar de propagarlas.
            registro["ok"] = not str(parseada).startswith("An error occurred while running the tool")
        return salida

    tool.on_invoke_tool = envoltura
    tool._eval_instrumentada = True  # type: ignore[attr-defined]


# Herramientas de los especialistas (objetos compartidos por todas las arquitecturas).
for _lista in (core_tools.TOOLS_FAQ, core_tools.TOOLS_CLIMA,
               core_tools.TOOLS_SEGURIDAD, core_tools.TOOLS_AGENDA):
    for _t in _lista:
        _instrumentar(_t, "especialista")


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------
def _es_rate_limit(exc: Exception) -> bool:
    texto = f"{type(exc).__name__} {exc}".lower()
    return "ratelimit" in texto or "rate limit" in texto or "429" in texto


def _es_tool_call_invalida(exc: Exception) -> bool:
    """gpt-oss en Groq a veces emite una llamada de herramienta mal formada
    (nombre con tokens '<|channel|>...' o sin el parámetro 'input'). Groq la
    rechaza con un 400 antes de que llegue al agente; repetir la petición suele
    bastar porque el modelo no es determinístico."""
    texto = f"{type(exc).__name__} {exc}".lower()
    return "tool call validation failed" in texto or "tool_use_failed" in texto


# Un único event loop para todas las llamadas del worker de promptfoo. El cliente
# AsyncOpenAI de core/config.py es global y queda ligado al loop donde se creó;
# con asyncio.run() se cerraba el loop al terminar cada caso y el siguiente
# fallaba con "RuntimeError: Event loop is closed".
_LOOP: asyncio.AbstractEventLoop | None = None


def _loop() -> asyncio.AbstractEventLoop:
    global _LOOP
    if _LOOP is None or _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


async def _ejecutar(pregunta: str) -> tuple[Any, list[dict], float, int]:
    intentos = 0
    while True:
        intentos += 1
        traza: list[dict] = []
        _traza.set(traza)
        orquestador = centralizada.construir_orquestador()
        for t in orquestador.tools:
            if isinstance(t, FunctionTool):
                _instrumentar(t, "orquestador")
        inicio = time.perf_counter()
        try:
            resultado = await Runner.run(
                orquestador,
                [{"role": "user", "content": pregunta}],
                max_turns=MAX_TURNOS,
            )
            return resultado, traza, (time.perf_counter() - inicio) * 1000, intentos
        except Exception as exc:  # noqa: BLE001
            if intentos < MAX_REINTENTOS:
                if _es_rate_limit(exc):
                    await asyncio.sleep(10 * intentos)
                    continue
                if _es_tool_call_invalida(exc):
                    await asyncio.sleep(2)
                    continue
            raise


def call_api(prompt: str, options: dict, context: dict) -> dict:
    variables = (context or {}).get("vars", {}) or {}
    pregunta = resolver_fechas(prompt)

    # 1) Clima reproducible
    escenario = str(variables.get("clima", "ideal")).lower()
    weather.obtener_clima = (
        _obtener_clima_real if escenario == "real" else _clima_fijo(escenario)
    )

    # 2) Agenda aislada en un archivo temporal
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "citas.json"
        previas = variables.get("citas_previas") or []
        if isinstance(previas, str):
            previas = json.loads(previas)
        previas = json.loads(resolver_fechas(json.dumps(previas, ensure_ascii=False)))
        ruta.write_text(json.dumps(previas, ensure_ascii=False), encoding="utf-8")
        scheduling.RUTA_CITAS = ruta

        try:
            resultado, traza, latencia_ms, intentos = _loop().run_until_complete(_ejecutar(pregunta))
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

        citas_finales = scheduling.listar()

    contexto = [
        r["salida"] for r in traza
        if r["tool"] == "consultar_faqs" and isinstance(r["salida"], str)
    ]

    uso = resultado.context_wrapper.usage
    return {
        "output": str(resultado.final_output),
        "latencyMs": round(latencia_ms),
        "tokenUsage": {
            "total": uso.total_tokens,
            "prompt": uso.input_tokens,
            "completion": uso.output_tokens,
            "numRequests": uso.requests,
        },
        "metadata": {
            "arquitectura": "centralizada",
            "pregunta_resuelta": pregunta,
            "fecha_hoy": date.today().isoformat(),
            "clima_escenario": escenario,
            "tool_calls": traza,
            "herramientas": [r["tool"] for r in traza],
            "contexto_recuperado": "\n\n---\n\n".join(contexto) or "(sin contexto recuperado)",
            "citas_finales": citas_finales,
            "intentos": intentos,
        },
    }


if __name__ == "__main__":
    # Prueba manual: python evals/provider.py "¿Cuánto cuesta un salto tándem?"
    texto = " ".join(sys.argv[1:]) or "¿Cuánto cuesta un salto tándem?"
    print(json.dumps(call_api(texto, {}, {"vars": {}}), ensure_ascii=False, indent=2))
