"""test_remediacion_clasificacion — clasificacion.py es un módulo
puro (sin sqlite3, sin red): casos de tabla directos, sin fixtures ni
bases temporales. Ver data-model.md de
specs/022-clasificacion-remediacion/, "Clasificación de remediación"."""

from __future__ import annotations

from remediacion import clasificacion
from tests.selftest import check


def test_clasificar_contenedor_critico_es_manual_con_cualquier_modo() -> None:
    criticos = {"homeassistant"}
    never_restart: set[str] = set()
    check(
        "crítico en modo automático (si lo hubiera) ⇒ manual",
        clasificacion.clasificar_contenedor("homeassistant", criticos, never_restart, "automatico") == "manual",
    )
    check(
        "crítico en modo manual ⇒ manual",
        clasificacion.clasificar_contenedor("homeassistant", criticos, never_restart, "manual") == "manual",
    )
    check(
        "crítico sin modo (None) ⇒ manual",
        clasificacion.clasificar_contenedor("homeassistant", criticos, never_restart, None) == "manual",
    )


def test_clasificar_contenedor_no_critico_es_ia_con_cualquier_modo() -> None:
    criticos: set[str] = set()
    never_restart: set[str] = set()
    check(
        "no crítico en modo manual ⇒ ia (FR-004: el modo no cambia la etiqueta)",
        clasificacion.clasificar_contenedor("beszel", criticos, never_restart, "manual") == "ia",
    )
    check(
        "no crítico en modo automático ⇒ ia",
        clasificacion.clasificar_contenedor("beszel", criticos, never_restart, "automatico") == "ia",
    )


def test_clasificar_contenedor_never_restart_es_manual() -> None:
    criticos: set[str] = set()
    never_restart = {"frigate"}
    check(
        "NEVER_RESTART ⇒ manual, igual que un crítico (FR-007)",
        clasificacion.clasificar_contenedor("frigate", criticos, never_restart, None) == "manual",
    )


def test_clasificar_log_automatica_solo_en_modo_automatico() -> None:
    check("modo automático ⇒ automatica (FR-005)", clasificacion.clasificar_log("automatico") == "automatica")
    check("modo manual ⇒ manual", clasificacion.clasificar_log("manual") == "manual")
