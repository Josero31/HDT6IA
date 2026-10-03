"""
Bucle de consola compartido.

Las tres arquitecturas usan exactamente este runner; lo único que le pasan es
el agente de entrada. En la arquitectura descentralizada se activa
`conservar_agente=True` para que el control permanezca en el último agente que
atendió (así el handoff persiste entre turnos).
"""

from __future__ import annotations

import asyncio

from agents import Agent, Runner

MAX_TURNOS = 20


def _banner(titulo: str, agentes: list[str]) -> None:
    ancho = 74
    print("=" * ancho)
    print(f" {titulo}")
    print("-" * ancho)
    print(" Agentes activos: " + ", ".join(agentes))
    print(" Escribe 'salir' para terminar.")
    print("=" * ancho)


async def _bucle(agente_inicial: Agent, titulo: str, agentes: list[str], conservar_agente: bool):
    _banner(titulo, agentes)
    historial: list = []
    agente_actual = agente_inicial

    while True:
        try:
            entrada = input("\nUsuario > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego.")
            return
        if not entrada:
            continue
        if entrada.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego.")
            return

        historial.append({"role": "user", "content": entrada})
        try:
            resultado = await Runner.run(agente_actual, historial, max_turns=MAX_TURNOS)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[error] {type(exc).__name__}: {exc}")
            historial.pop()
            continue

        historial = resultado.to_input_list()
        if conservar_agente:
            agente_actual = resultado.last_agent

        etiqueta = resultado.last_agent.name if conservar_agente else agente_inicial.name
        print(f"\n{etiqueta} > {resultado.final_output}")


def run_cli(
    agente_inicial: Agent,
    titulo: str,
    agentes: list[str],
    conservar_agente: bool = False,
) -> None:
    asyncio.run(_bucle(agente_inicial, titulo, agentes, conservar_agente))
