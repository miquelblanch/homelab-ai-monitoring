"""clasificacion — Manual/Automática/IA por componente. Ver data-model.md
de specs/022-clasificacion-remediacion/.

Módulo puro: sin sqlite3, sin red, sin efectos secundarios. La
clasificación nunca se persiste de forma independiente (FR-002) — se
deriva siempre, en el momento de mostrarla, de la configuración de
remediación y la criticidad reales ya existentes.
"""

from __future__ import annotations


def clasificar_contenedor(
    nombre: str,
    criticos: set[str],
    never_restart: set[str],
    modo: str | None,
) -> str:
    """"manual" si `nombre` está en `criticos` o `never_restart` — el
    modo se ignora en ese caso (FR-006/FR-007): un contenedor crítico
    siempre es Manual, tenga o no una propuesta real de DeepSeek
    detrás. Si no, "ia" siempre (FR-004) — con independencia de `modo`,
    que aquí solo distingue si la ejecución final es automática o
    espera aprobación, no quién decide."""
    if nombre in criticos or nombre in never_restart:
        return "manual"
    return "ia"


def clasificar_log(modo: str) -> str:
    """"automatica" si `modo == "automatico"`, si no "manual" (FR-005)
    — el eje crítico/no crítico no aplica a los logs vigilados."""
    return "automatica" if modo == "automatico" else "manual"
