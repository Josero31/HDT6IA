"""
ARQUITECTURA 2 — ORQUESTACIÓN JERÁRQUICA

Tres niveles. El director solo conversa con dos gerencias; cada gerencia
coordina a sus propios especialistas. El control fluye hacia abajo y los
resultados se agregan hacia arriba.

                    ┌──────────────────────┐
                    │   Director (N1)      │
                    └───────┬──────────────┘
                 ┌──────────┴──────────┐
        ┌────────▼────────┐   ┌────────▼─────────┐
        │ Ger. Información│   │ Ger. Operaciones │   (N2)
        └───┬─────────┬───┘   └────┬─────────┬───┘
          FAQs      Clima      Seguridad   Agenda     (N3)

Los mismos agentes especialistas de `core.agents_base` se reutilizan sin
cambios: solo cambia quién los tiene como herramienta.
"""

from agents import Agent

from core import prompts
from core.agents_base import agente_agenda, agente_clima, agente_faqs, agente_seguridad
from core.config import get_model
from core.runner import run_cli


def construir_gerencia_informacion() -> Agent:
    return Agent(
        name="Gerencia de Información",
        instructions=prompts.GERENTE_INFORMACION,
        model=get_model(),
        handoff_description="Coordina FAQs y pronóstico meteorológico.",
        tools=[
            agente_faqs().as_tool(
                tool_name="especialista_faqs",
                tool_description="Responde preguntas de la base de conocimiento.",
            ),
            agente_clima().as_tool(
                tool_name="especialista_clima",
                tool_description="Devuelve los valores de Open-Meteo para una fecha.",
            ),
        ],
    )


def construir_gerencia_operaciones() -> Agent:
    return Agent(
        name="Gerencia de Operaciones",
        instructions=prompts.GERENTE_OPERACIONES,
        model=get_model(),
        handoff_description="Coordina el dictamen de seguridad y el registro de citas.",
        tools=[
            agente_seguridad().as_tool(
                tool_name="especialista_seguridad",
                tool_description="Emite el dictamen IDEAL / MARGINAL / PROHIBIDO.",
            ),
            agente_agenda().as_tool(
                tool_name="especialista_agenda",
                tool_description="Consulta disponibilidad y registra o cancela citas.",
            ),
        ],
    )


def construir_director() -> Agent:
    return Agent(
        name="Director de Operaciones",
        instructions=prompts.DIRECTOR,
        model=get_model(),
        tools=[
            construir_gerencia_informacion().as_tool(
                tool_name="gerencia_de_informacion",
                tool_description="Preguntas de la base de conocimiento y datos meteorológicos.",
            ),
            construir_gerencia_operaciones().as_tool(
                tool_name="gerencia_de_operaciones",
                tool_description="Dictamen de seguridad de vuelo y gestión de citas.",
            ),
        ],
    )


if __name__ == "__main__":
    run_cli(
        construir_director(),
        "PARACHUTE S.A. — Arquitectura JERÁRQUICA (3 niveles)",
        [
            "Director",
            "Ger. Información [FAQs, Clima]",
            "Ger. Operaciones [Seguridad, Agenda]",
        ],
    )
