"""
Persistencia de citas.

Repositorio muy simple sobre un archivo JSON. Está aislado para que mañana se
pueda cambiar por una base de datos o por el CRM de Parachute S.A. sin tocar
agentes ni arquitecturas.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from .config import HORARIOS_DISPONIBLES, RUTA_CITAS
from .domain import Cita, ErrorDeNegocio


def _cargar() -> list[dict]:
    if not RUTA_CITAS.exists():
        return []
    try:
        return json.loads(RUTA_CITAS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _guardar(citas: list[dict]) -> None:
    RUTA_CITAS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_CITAS.write_text(
        json.dumps(citas, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def horarios_libres(fecha: str) -> list[str]:
    ocupados = {c["hora"] for c in _cargar() if c["fecha"] == fecha}
    return [h for h in HORARIOS_DISPONIBLES if h not in ocupados]


def agendar(nombre: str, telefono: str, fecha: str, hora: str, nivel_clima: str) -> Cita:
    """Registra la cita. Rechaza si el clima fue declarado PROHIBIDO o el cupo está tomado."""
    if nivel_clima.upper() == "PROHIBIDO":
        raise ErrorDeNegocio(
            f"No se puede agendar el {fecha}: las condiciones meteorológicas fueron "
            "declaradas NO SEGURAS."
        )
    if hora not in HORARIOS_DISPONIBLES:
        raise ErrorDeNegocio(
            f"'{hora}' no es un horario válido. Disponibles: {', '.join(HORARIOS_DISPONIBLES)}."
        )
    if hora not in horarios_libres(fecha):
        raise ErrorDeNegocio(
            f"El horario {hora} del {fecha} ya está ocupado. "
            f"Libres: {', '.join(horarios_libres(fecha)) or 'ninguno'}."
        )

    cita = Cita(
        id=uuid.uuid4().hex[:8].upper(),
        nombre=nombre.strip(),
        telefono=telefono.strip(),
        fecha=fecha,
        hora=hora,
        nivel_clima=nivel_clima.upper(),
        creada_en=datetime.now().isoformat(timespec="seconds"),
    )
    citas = _cargar()
    citas.append(cita.to_dict())
    _guardar(citas)
    return cita


def listar(fecha: str = "") -> list[dict]:
    citas = _cargar()
    return [c for c in citas if not fecha or c["fecha"] == fecha]


def cancelar(id_cita: str) -> bool:
    citas = _cargar()
    restantes = [c for c in citas if c["id"].upper() != id_cita.upper()]
    if len(restantes) == len(citas):
        return False
    _guardar(restantes)
    return True
