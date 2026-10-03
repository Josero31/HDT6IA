"""
Motor de reglas de seguridad de salto.

Lógica determinística: NO la decide el LLM. El agente solo la invoca y
comunica el resultado. Así el veredicto es auditable y reproducible, y un
cambio de umbral se hace en un único lugar.
"""

from __future__ import annotations

from .domain import ClimaDia, Criterio, Nivel, Veredicto

# Umbrales entregados por Parachute S.A.
VIENTO_IDEAL_MAX = 20.0  # km/h
VIENTO_MARGINAL_MAX = 28.0  # km/h
RAFAGA_MAX = 35.0  # km/h
PRECIPITACION_MAX = 0.0  # mm
NUBES_IDEAL_MAX = 30.0  # %
NUBES_MARGINAL_MAX = 75.0  # %


def _viento(valor: float) -> Criterio:
    if valor > VIENTO_MARGINAL_MAX:
        nivel, exp = Nivel.PROHIBIDO, (
            f"{valor:.1f} km/h supera los {VIENTO_MARGINAL_MAX:.0f} km/h: el salto es "
            "muy difícil de controlar."
        )
    elif valor >= VIENTO_IDEAL_MAX:
        nivel, exp = Nivel.MARGINAL, (
            f"{valor:.1f} km/h está en la franja {VIENTO_IDEAL_MAX:.0f}-"
            f"{VIENTO_MARGINAL_MAX:.0f} km/h: solo tándem con instructor experimentado."
        )
    else:
        nivel, exp = Nivel.IDEAL, f"{valor:.1f} km/h está por debajo de {VIENTO_IDEAL_MAX:.0f} km/h."
    return Criterio("Viento en superficie (10 m)", valor, "km/h", nivel, exp)


def _rafagas(valor: float) -> Criterio:
    if valor > RAFAGA_MAX:
        nivel, exp = Nivel.PROHIBIDO, (
            f"Ráfagas de {valor:.1f} km/h superan el límite de {RAFAGA_MAX:.0f} km/h."
        )
    else:
        nivel, exp = Nivel.IDEAL, f"Ráfagas de {valor:.1f} km/h dentro del límite."
    return Criterio("Ráfagas de viento (10 m)", valor, "km/h", nivel, exp)


def _precipitacion(valor: float) -> Criterio:
    if valor > PRECIPITACION_MAX:
        nivel, exp = Nivel.PROHIBIDO, (
            f"Se pronostican {valor:.1f} mm de precipitación; saltar con lluvia daña el "
            "equipo y lastima la piel."
        )
    else:
        nivel, exp = Nivel.IDEAL, "Sin precipitación pronosticada."
    return Criterio("Precipitación", valor, "mm", nivel, exp)


def _nubes(valor: float) -> Criterio:
    if valor > NUBES_MARGINAL_MAX:
        nivel, exp = Nivel.PROHIBIDO, (
            f"{valor:.0f}% de cobertura implica techo de nubes bajo: impide las reglas "
            "de vuelo visual."
        )
    elif valor >= NUBES_IDEAL_MAX:
        nivel, exp = Nivel.MARGINAL, f"{valor:.0f}% de cobertura: nubes dispersas."
    else:
        nivel, exp = Nivel.IDEAL, f"{valor:.0f}% de cobertura: visibilidad clara."
    return Criterio("Cobertura de nubes / visibilidad", valor, "%", nivel, exp)


def evaluar(clima: ClimaDia) -> Veredicto:
    """Aplica las cuatro reglas y consolida con el criterio más restrictivo."""
    criterios = [
        _viento(clima.viento_superficie_10m),
        _rafagas(clima.rafagas_10m),
        _precipitacion(clima.precipitacion),
        _nubes(clima.cobertura_nubes),
    ]
    peor = max(criterios, key=lambda c: c.nivel.orden).nivel

    if peor is Nivel.PROHIBIDO:
        motivos = "; ".join(c.explicacion for c in criterios if c.nivel is Nivel.PROHIBIDO)
        resumen = f"NO SEGURO para saltar el {clima.fecha}. Motivo(s): {motivos}"
    elif peor is Nivel.MARGINAL:
        motivos = "; ".join(c.explicacion for c in criterios if c.nivel is Nivel.MARGINAL)
        resumen = (
            f"Condiciones MARGINALES el {clima.fecha}: {motivos} "
            "Solo se autoriza salto tándem con instructor experimentado."
        )
    else:
        resumen = f"Condiciones IDEALES para saltar el {clima.fecha}."

    return Veredicto(
        fecha=clima.fecha,
        nivel=peor,
        apto=peor is not Nivel.PROHIBIDO,
        criterios=criterios,
        resumen=resumen,
    )


def evaluar_valores(
    viento_superficie_10m: float,
    rafagas_10m: float,
    precipitacion: float,
    cobertura_nubes: float,
    fecha: str = "",
) -> Veredicto:
    """Variante que evalúa números sueltos (útil cuando el clima ya fue consultado)."""
    clima = ClimaDia(
        fecha=fecha,
        fuente="manual",
        temperatura_2m=0.0,
        precipitacion=precipitacion,
        cobertura_nubes=cobertura_nubes,
        viento_superficie_10m=viento_superficie_10m,
        rafagas_10m=rafagas_10m,
        latitud=0.0,
        longitud=0.0,
    )
    return evaluar(clima)
