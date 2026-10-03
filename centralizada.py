"""
ARQUITECTURA 1 — ORQUESTACIÓN CENTRALIZADA

Un único orquestador concentra el control. Los cuatro especialistas se exponen
como herramientas (`as_tool`) y nunca hablan entre sí ni con el cliente: el
orquestador los invoca, recibe su salida y redacta la respuesta final.

        ┌────────────────────────────┐
        │   Orquestador (1 nivel)    │
        └──┬────────┬────────┬───────┘
           │        │        │       └────────┐
        FAQs      Clima   Seguridad         Agenda      (agentes-herramienta)
"""

from agents import Agent

from core import prompts
from core.agents_base import agente_agenda, agente_clima, agente_faqs, agente_seguridad
from core.config import get_model
from core.runner import run_cli


def construir_orquestador() -> Agent:
    faqs = agente_faqs()
    clima = agente_clima()
    seguridad = agente_seguridad()
    agenda = agente_agenda()

    return Agent(
        name="Orquestador Parachute",
        instructions=prompts.CENTRALIZADO,
        model=get_model(),
        tools=[
            faqs.as_tool(
                tool_name="consultar_informacion",
                tool_description="Consulta la base de FAQs de la empresa (precios, requisitos, políticas).",
            ),
            clima.as_tool(
                tool_name="consultar_pronostico",
                tool_description="Obtiene de Open-Meteo el clima de la zona de aterrizaje para una fecha.",
            ),
            seguridad.as_tool(
                tool_name="dictaminar_seguridad",
                tool_description="Evalúa si las condiciones son IDEAL, MARGINAL o PROHIBIDO para saltar.",
            ),
            agenda.as_tool(
                tool_name="gestionar_agenda",
                tool_description="Consulta disponibilidad y registra, lista o cancela citas de salto.",
            ),
        ],
    )


if __name__ == "__main__":
    run_cli(
        construir_orquestador(),
        "PARACHUTE S.A. — Arquitectura CENTRALIZADA (agents-as-tools)",
        ["Orquestador", "FAQs", "Clima", "Seguridad", "Agenda"],
    )
