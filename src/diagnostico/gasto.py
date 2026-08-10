"""gasto — Cortacircuitos de gasto diario de DeepSeek, a partir de tokens
reales (FR-009, FR-010). Ver research.md §6.

Nunca consulta la facturación de la API — el coste se calcula localmente
a partir de los tokens que cada respuesta reporta, contra una tabla de
precios que hay que revisar si DeepSeek cambia su tarifa (research.md §6,
mismo espíritu que otros "revisar periódicamente" del proyecto).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date

from . import store

# EUR por millón de tokens — revisar contra el precio vigente de DeepSeek
# (research.md §6). Valores de partida a la espera de confirmación con la
# tarifa real en el momento de desplegar.
PRECIOS_EUR_POR_MILLON_TOKENS = {
    "entrada": 0.27,
    "salida": 1.10,
}

_LIMITE_POR_DEFECTO_EUR = 5.0


def limite_diario_eur() -> float:
    return float(os.environ.get("DIAGNOSTICO_LIMITE_EUR_DIA", _LIMITE_POR_DEFECTO_EUR))


def dia_actual() -> str:
    return date.today().isoformat()


def calcular_coste_eur(tokens_entrada: int, tokens_salida: int) -> float:
    return (
        tokens_entrada * PRECIOS_EUR_POR_MILLON_TOKENS["entrada"]
        + tokens_salida * PRECIOS_EUR_POR_MILLON_TOKENS["salida"]
    ) / 1_000_000


def gasto_hoy(conn: sqlite3.Connection) -> float:
    fila = store.get_gasto_diario(conn, dia_actual())
    return fila["coste_eur_acumulado"] if fila else 0.0


def hay_presupuesto(conn: sqlite3.Connection, tokens_entrada_reales: int) -> bool:
    """FR-010: comprueba si una llamada nueva se sabe de antemano que
    superaría el límite diario, usando el mismo `max_tokens` real que se
    envía a la API como estimación del peor caso de salida (research.md
    §6, hallazgo B1 de /speckit-analyze — no un margen "prudente" sin
    definir)."""
    from .deepseek import DIAGNOSTICO_DEEPSEEK_MAX_TOKENS

    coste_estimado = calcular_coste_eur(tokens_entrada_reales, DIAGNOSTICO_DEEPSEEK_MAX_TOKENS)
    return gasto_hoy(conn) + coste_estimado <= limite_diario_eur()


def registrar_coste(conn: sqlite3.Connection, tokens_entrada: int, tokens_salida: int) -> float:
    """Registra el coste EFECTIVO (nunca la estimación previa de
    `hay_presupuesto`) en el acumulado del día. Devuelve el coste de esta
    llamada en euros."""
    coste = calcular_coste_eur(tokens_entrada, tokens_salida)
    store.upsert_gasto_diario(conn, dia_actual(), coste, limite_diario_eur())
    return coste
