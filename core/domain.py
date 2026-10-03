"""
Modelos de dominio.

Son estructuras puras (sin dependencia del SDK de agentes) que viajan entre
la capa de integraciones y la capa de agentes. Si mañana Parachute S.A. pide
un requerimiento nuevo, se extiende aquí una sola vez.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from enum import Enum
from typing import Any


class Nivel(str, Enum):
    """Veredicto de una condición meteorológica individual o del día completo."""

    IDEAL = "IDEAL"
    MARGINAL = "MARGINAL"
    PROHIBIDO = "PROHIBIDO"

    @property
    def orden(self) -> int:
        return {"IDEAL": 0, "MARGINAL": 1, "PROHIBIDO": 2}[self.value]


@dataclass
class ClimaDia:
    """Snapshot meteorológico normalizado para una fecha y un punto geográfico."""

    fecha: str
    fuente: str  # "current" o "daily" de Open-Meteo
    temperatura_2m: float  # °C
    precipitacion: float  # mm
    cobertura_nubes: float  # %
    viento_superficie_10m: float  # km/h
    rafagas_10m: float  # km/h
    latitud: float
    longitud: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Criterio:
    """Resultado de aplicar una regla de seguridad a una variable."""

    nombre: str
    valor: float
    unidad: str
    nivel: Nivel
    explicacion: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["nivel"] = self.nivel.value
        return d


@dataclass
class Veredicto:
    """Decisión final sobre si un día es apto para saltar."""

    fecha: str
    nivel: Nivel
    apto: bool
    criterios: list[Criterio] = field(default_factory=list)
    resumen: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fecha": self.fecha,
            "nivel": self.nivel.value,
            "apto": self.apto,
            "resumen": self.resumen,
            "criterios": [c.to_dict() for c in self.criterios],
        }


@dataclass
class Cita:
    """Cita de salto agendada."""

    id: str
    nombre: str
    telefono: str
    fecha: str
    hora: str
    nivel_clima: str
    creada_en: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ErrorDeNegocio(Exception):
    """Error esperado y comunicable al usuario (no es una falla técnica)."""
