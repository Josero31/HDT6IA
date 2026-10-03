"""
Fábrica de agentes especialistas.

Los cuatro especialistas (FAQs, clima, seguridad, agenda) se construyen aquí
una sola vez. Las tres arquitecturas los reutilizan tal cual y solo cambian
la forma de conectarlos:

  - centralizada  -> los expone como herramientas de un orquestador (as_tool)
  - jerárquica    -> los expone como herramientas de gerencias intermedias
  - descentralizada -> los conecta entre sí como pares (handoffs)
"""

from __future__ import annotations

from agents import Agent

from . import prompts, tools
from .config import get_model


def _agente(nombre: str, instrucciones: str, herramientas: list, descripcion: str) -> Agent:
    return Agent(
        name=nombre,
        instructions=instrucciones,
        tools=herramientas,
        handoff_description=descripcion,
        model=get_model(),
    )


def agente_faqs(instrucciones: str | None = None) -> Agent:
    return _agente(
        "Especialista FAQs",
        instrucciones or prompts.FAQ,
        tools.TOOLS_FAQ,
        "Responde preguntas sobre precios, requisitos, políticas y equipo de la empresa.",
    )


def agente_clima(instrucciones: str | None = None) -> Agent:
    return _agente(
        "Especialista Clima",
        instrucciones or prompts.CLIMA,
        tools.TOOLS_CLIMA,
        "Obtiene de Open-Meteo el pronóstico de la zona de aterrizaje para una fecha.",
    )


def agente_seguridad(instrucciones: str | None = None) -> Agent:
    return _agente(
        "Oficial de Seguridad",
        instrucciones or prompts.SEGURIDAD,
        tools.TOOLS_SEGURIDAD,
        "Dictamina si un día es IDEAL, MARGINAL o PROHIBIDO para saltar.",
    )


def agente_agenda(instrucciones: str | None = None) -> Agent:
    return _agente(
        "Especialista Agenda",
        instrucciones or prompts.AGENDA,
        tools.TOOLS_AGENDA,
        "Consulta disponibilidad, registra, lista y cancela citas de salto.",
    )
