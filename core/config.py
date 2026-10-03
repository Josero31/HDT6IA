"""
Configuración central del sistema.

Aquí vive TODO lo que es específico del proveedor de LLM y del negocio.
Las tres arquitecturas (centralizada, jerárquica y descentralizada) importan
de este módulo, de modo que cambiar de modelo o de proveedor no obliga a
tocar ninguna de las tres implementaciones.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel, set_tracing_disabled

load_dotenv()

# --------------------------------------------------------------------------
# Proveedor de LLM (cualquiera compatible con la API de OpenAI: Groq, NVIDIA,
# OpenAI, Ollama, etc.)
# --------------------------------------------------------------------------
BASE_URL = os.getenv("BASE_URL", "https://api.groq.com/openai/v1")
API_KEY = os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-120b")

# El tracing del SDK sube datos a la plataforma de OpenAI y exige OPENAI_API_KEY.
# Como estamos usando un proveedor alterno, se desactiva.
set_tracing_disabled(True)

_client: AsyncOpenAI | None = None


def get_model() -> OpenAIChatCompletionsModel:
    """Devuelve el modelo compartido por todos los agentes de cualquier arquitectura."""
    global _client
    if not API_KEY:
        raise RuntimeError(
            "Falta la variable API_KEY. Copia .env.example a .env y coloca tu llave."
        )
    if _client is None:
        _client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    return OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=_client)


# --------------------------------------------------------------------------
# Constantes del negocio (Parachute S.A.)
# --------------------------------------------------------------------------
EMPRESA = "Parachute S.A."

# Coordenadas del lugar de aterrizaje indicadas por el cliente.
LATITUD = 14.013722
LONGITUD = -90.771611
ZONA_HORARIA = "America/Guatemala"

# Open-Meteo solo entrega pronóstico hasta 16 días hacia adelante.
DIAS_MAX_PRONOSTICO = 16

# Horario de operación para las citas.
HORARIOS_DISPONIBLES = ["07:00", "08:30", "10:00", "11:30", "14:00", "15:30"]

# Rutas de datos
RAIZ = Path(__file__).resolve().parent.parent
RUTA_FAQS = RAIZ / "data" / "faqs.md"
RUTA_CITAS = RAIZ / "data" / "citas.json"
