"""
Integración con Open-Meteo.

Esta es la ÚNICA parte del proyecto que conoce la API de clima. Devuelve un
`ClimaDia` normalizado, así que ni las herramientas ni los agentes ni las tres
arquitecturas dependen del formato de Open-Meteo.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import requests

from .config import DIAS_MAX_PRONOSTICO, LATITUD, LONGITUD, ZONA_HORARIA
from .domain import ClimaDia, ErrorDeNegocio

URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 20

# Variables pedidas por el cliente, traducidas al nombre real de cada modo
# de la API (Open-Meteo usa nombres distintos en `current` y en `daily`).
VARIABLES_CURRENT = [
    "temperature_2m",
    "precipitation",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
]
VARIABLES_DAILY = [
    "temperature_2m_max",
    "precipitation_sum",
    "cloud_cover_mean",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
]
# Juego reducido por si el modelo seleccionado no publica `cloud_cover_mean`.
VARIABLES_DAILY_FALLBACK = [
    "temperature_2m_max",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
]


def parsear_fecha(texto: str) -> date:
    """Acepta 'YYYY-MM-DD', 'hoy' o 'mañana'. Lanza ErrorDeNegocio si no se entiende."""
    limpio = (texto or "").strip().lower()
    hoy = date.today()
    if limpio in {"hoy", "today"}:
        return hoy
    if limpio in {"mañana", "manana", "tomorrow"}:
        return hoy + timedelta(days=1)
    try:
        return datetime.strptime(limpio, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ErrorDeNegocio(
            f"No pude interpretar la fecha '{texto}'. Usa el formato YYYY-MM-DD."
        ) from exc


def validar_horizonte(fecha: date) -> None:
    """Regla del cliente: Open-Meteo solo pronostica 16 días hacia adelante."""
    hoy = date.today()
    if fecha < hoy:
        raise ErrorDeNegocio(
            f"La fecha {fecha.isoformat()} ya pasó. Elige una fecha de hoy en adelante."
        )
    delta = (fecha - hoy).days
    if delta > DIAS_MAX_PRONOSTICO:
        limite = (hoy + timedelta(days=DIAS_MAX_PRONOSTICO)).isoformat()
        raise ErrorDeNegocio(
            f"No es posible calendarizar para {fecha.isoformat()}: el pronóstico de "
            f"Open-Meteo solo llega a {DIAS_MAX_PRONOSTICO} días ({delta} días solicitados). "
            f"La fecha máxima que puedo evaluar hoy es {limite}."
        )


def _pedir(params: dict) -> dict:
    try:
        respuesta = requests.get(URL, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise ErrorDeNegocio(f"No se pudo contactar a Open-Meteo: {exc}") from exc
    if respuesta.status_code != 200:
        detalle = ""
        try:
            detalle = respuesta.json().get("reason", "")
        except Exception:  # noqa: BLE001
            detalle = respuesta.text[:200]
        raise ErrorDeNegocio(f"Open-Meteo respondió {respuesta.status_code}: {detalle}")
    return respuesta.json()


def obtener_clima(
    texto_fecha: str,
    latitud: float = LATITUD,
    longitud: float = LONGITUD,
) -> ClimaDia:
    """
    Consulta Open-Meteo y devuelve el snapshot del día solicitado.

    Usa `current` cuando la fecha es hoy (dato más fino) y `daily` para
    cualquier otro día dentro de la ventana de 16 días.
    """
    fecha = parsear_fecha(texto_fecha)
    validar_horizonte(fecha)

    base = {
        "latitude": latitud,
        "longitude": longitud,
        "timezone": ZONA_HORARIA,
        "wind_speed_unit": "kmh",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
    }

    if fecha == date.today():
        datos = _pedir({**base, "current": ",".join(VARIABLES_CURRENT)})
        actual = datos.get("current", {})
        return ClimaDia(
            fecha=fecha.isoformat(),
            fuente="current",
            temperatura_2m=float(actual.get("temperature_2m") or 0.0),
            precipitacion=float(actual.get("precipitation") or 0.0),
            cobertura_nubes=float(actual.get("cloud_cover") or 0.0),
            viento_superficie_10m=float(actual.get("wind_speed_10m") or 0.0),
            rafagas_10m=float(actual.get("wind_gusts_10m") or 0.0),
            latitud=float(datos.get("latitude", latitud)),
            longitud=float(datos.get("longitude", longitud)),
        )

    params = {
        **base,
        "daily": ",".join(VARIABLES_DAILY),
        "start_date": fecha.isoformat(),
        "end_date": fecha.isoformat(),
    }
    try:
        datos = _pedir(params)
    except ErrorDeNegocio:
        # Algunos modelos no exponen cloud_cover_mean: se reintenta sin esa
        # variable y la nubosidad se promedia a partir de los datos horarios.
        params["daily"] = ",".join(VARIABLES_DAILY_FALLBACK)
        params["hourly"] = "cloud_cover"
        datos = _pedir(params)

    diario = datos.get("daily", {})
    if not diario.get("time"):
        raise ErrorDeNegocio(f"Open-Meteo no devolvió datos para {fecha.isoformat()}.")

    nubes = diario.get("cloud_cover_mean", [None])[0]
    if nubes is None:
        horarias = datos.get("hourly", {}).get("cloud_cover", [])
        validas = [v for v in horarias if v is not None]
        nubes = sum(validas) / len(validas) if validas else 0.0

    return ClimaDia(
        fecha=fecha.isoformat(),
        fuente="daily",
        temperatura_2m=float(diario.get("temperature_2m_max", [0.0])[0] or 0.0),
        precipitacion=float(diario.get("precipitation_sum", [0.0])[0] or 0.0),
        cobertura_nubes=float(nubes),
        viento_superficie_10m=float(diario.get("wind_speed_10m_max", [0.0])[0] or 0.0),
        rafagas_10m=float(diario.get("wind_gusts_10m_max", [0.0])[0] or 0.0),
        latitud=float(datos.get("latitude", latitud)),
        longitud=float(datos.get("longitude", longitud)),
    )
