"""
Base de conocimiento de FAQs (lo construido en la hoja anterior).

Recuperación ligera por coincidencia de términos sobre los bloques del
archivo `data/faqs.md`. El documento es pequeño, así que no hace falta una
base vectorial: se devuelven los bloques más relevantes como contexto.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from .config import RUTA_FAQS

VACIAS = {
    "de", "la", "el", "los", "las", "un", "una", "y", "o", "que", "en", "para",
    "con", "por", "del", "al", "se", "es", "son", "cual", "cuales", "como",
    "cuanto", "cuanta", "cuantos", "donde", "cuando", "qué", "the", "a",
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def _tokens(texto: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", _normalizar(texto)) if t not in VACIAS and len(t) > 2}


@lru_cache(maxsize=1)
def _bloques() -> list[str]:
    if not RUTA_FAQS.exists():
        return []
    crudo = RUTA_FAQS.read_text(encoding="utf-8")
    partes = [p.strip() for p in re.split(r"\n(?=##\s)", crudo) if p.strip()]
    return partes


def buscar(pregunta: str, k: int = 3) -> str:
    """Devuelve los k bloques de FAQ más relevantes, ya formateados."""
    bloques = _bloques()
    if not bloques:
        return "La base de conocimiento de FAQs no está disponible (falta data/faqs.md)."

    consulta = _tokens(pregunta)
    puntuados = []
    for bloque in bloques:
        score = len(consulta & _tokens(bloque))
        if score:
            puntuados.append((score, bloque))

    if not puntuados:
        return (
            "No se encontró información relacionada en la base de FAQs. "
            "Indica al usuario que un asesor humano lo contactará."
        )

    puntuados.sort(key=lambda x: x[0], reverse=True)
    elegidos = [b for _, b in puntuados[:k]]
    return "\n\n---\n\n".join(elegidos)


def documento_completo() -> str:
    return "\n\n".join(_bloques())
