"""evidencia — Reúne evidencia real del homelab para un episodio y la
congela en un snapshot (FR-002, FR-003 de 007). Paquete partido por
origen desde specs/023-evidencia-por-origen/ — cada uno de los diez
orígenes vive en su propio módulo (`contenedor`, `disco`, `ha`,
`backup`, `relay`, `inventario`, `host_externo`, `hub_beszel`,
`agente`, `latido`), y lo que varios orígenes usan de verdad a la vez
vive en `_compartido` (conexión a `homelab.db`, subprocesos de Docker
de solo lectura, acceso al hub de Beszel — nunca un origen más, ver
FR-006 de 023).

Este `__init__.py` es una fachada de compatibilidad: reexporta
exactamente los nombres que los tres consumidores reales usan hoy
(`diagnostico/cli.py`, `remediacion/acciones.py`,
`diagnostico/deepseek.py` — ver contracts/fachada-evidencia.md de 023),
para que ninguno de los tres tenga que cambiar cómo importa. Cualquier
función privada de un origen concreto se usa, fuera de su propio
módulo, solo desde su test de origen correspondiente — nunca desde
aquí ni desde otro origen.
"""

from __future__ import annotations

from .agente import congelar_agente_vivo
from .backup import congelar_backup_historico, congelar_backup_vivo
from .contenedor import congelar_historico, congelar_vivo
from .disco import congelar_disco_historico, congelar_disco_vivo
from .ha import congelar_ha_historico, congelar_ha_vivo
from .host_externo import congelar_host_externo_historico, congelar_host_externo_vivo
from .hub_beszel import congelar_hub_beszel_historico, congelar_hub_beszel_vivo
from .inventario import congelar_inventario_historico, congelar_inventario_vivo
from .latido import congelar_latido_vivo
from .relay import (
    congelar_relay_historico,
    congelar_relay_vivo,
    listar_nombres_relay,
    nombres_relay_evidenciados,
)

__all__ = [
    "congelar_agente_vivo",
    "congelar_backup_historico",
    "congelar_backup_vivo",
    "congelar_disco_historico",
    "congelar_disco_vivo",
    "congelar_ha_historico",
    "congelar_ha_vivo",
    "congelar_historico",
    "congelar_host_externo_historico",
    "congelar_host_externo_vivo",
    "congelar_hub_beszel_historico",
    "congelar_hub_beszel_vivo",
    "congelar_inventario_historico",
    "congelar_inventario_vivo",
    "congelar_latido_vivo",
    "congelar_relay_historico",
    "congelar_relay_vivo",
    "congelar_vivo",
    "listar_nombres_relay",
    "nombres_relay_evidenciados",
]
