"""
ARQUITECTURA 3 — ORQUESTACIÓN DESCENTRALIZADA

No hay coordinador. Cinco agentes pares se transfieren el control entre sí con
`handoffs`. El agente que recibe el handoff se queda con la conversación
completa y responde directamente al cliente.

        Recepción ⇄ FAQs
            ⇵         ⇵
          Clima  ⇄  Seguridad  ⇄  Agenda
              (todos pueden devolver a Recepción)

Como el control persiste entre turnos, el runner se ejecuta con
`conservar_agente=True`: el siguiente mensaje del usuario lo atiende el último
agente que quedó al mando.
"""

from agents import Agent

from core import prompts
from core.agents_base import agente_agenda, agente_clima, agente_faqs, agente_seguridad
from core.config import get_model
from core.runner import run_cli


def construir_red() -> Agent:
    # Mismos especialistas, con el aditivo de instrucciones para operar en red.
    faqs = agente_faqs(prompts.FAQ_DESC)
    clima = agente_clima(prompts.CLIMA_DESC)
    seguridad = agente_seguridad(prompts.SEGURIDAD_DESC)
    agenda = agente_agenda(prompts.AGENDA_DESC)

    recepcion = Agent(
        name="Recepción",
        instructions=prompts.RECEPCION,
        model=get_model(),
        handoff_description="Primer contacto: entiende la intención del cliente.",
    )

    # Grafo de transferencias entre pares (no hay jerarquía).
    recepcion.handoffs = [faqs, clima, seguridad, agenda]
    faqs.handoffs = [recepcion, clima, agenda]
    clima.handoffs = [seguridad, faqs, recepcion]
    seguridad.handoffs = [agenda, clima, recepcion]
    agenda.handoffs = [clima, seguridad, faqs, recepcion]

    return recepcion


if __name__ == "__main__":
    run_cli(
        construir_red(),
        "PARACHUTE S.A. — Arquitectura DESCENTRALIZADA (handoffs)",
        ["Recepción", "FAQs", "Clima", "Seguridad", "Agenda"],
        conservar_agente=True,
    )
