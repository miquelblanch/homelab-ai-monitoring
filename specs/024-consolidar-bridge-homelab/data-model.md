# Phase 1 — Data Model: Puente Único hacia los Scripts del Homelab

No hay modelo de datos nuevo. Este documento mapea las entidades de
`spec.md` (Pieza compartida, Pieza exclusiva, Dependencia entre
paquetes) al inventario exacto de qué función va a cada módulo,
verificado por uso real (`research.md`), no por el nombre.

## `src/_homelab_bridge_common.py` (nuevo, importado por los 3 paquetes)

| Elemento | Origen | Motivo |
|---|---|---|
| Bootstrap `HOMELAB_SCRIPTS_DIR` / `sys.path` | idéntico en los 3 hoy | los 3 lo necesitan para cualquier script externo |
| Handle `_homelab_secrets` | idéntico en los 3 hoy | los 3 importan `homelab_secrets` hoy |
| Handle `_docker_monitor` | idéntico en los 3 hoy | los 3 importan `docker_monitor` hoy |
| `get_secret(key, default)` | diagnostico + inventory, idénticas | — |
| `telegram_credentials()` | inventory + remediacion, idénticas | — |
| `docker_never_restart()` | los 3, idénticas | — |
| `docker_critical()` | diagnostico + inventory, idénticas — **la base**, sin el hook de remediacion | remediacion la envuelve, no la reexporta tal cual (research.md §3) |

## `src/_homelab_bridge_heartbeat.py` (nuevo, solo diagnostico + inventory)

| Elemento | Origen | Motivo |
|---|---|---|
| Handle `_heartbeat` | idéntico en diagnostico + inventory | remediacion nunca lo importa — no puede vivir en `_common.py` (research.md §1) |
| `record_heartbeat(job, status, detail)` | diagnostico + inventory, idénticas | — |

## `src/diagnostico/_homelab_bridge.py` (fachada, más corto)

| Público (reexportado) | De dónde |
|---|---|
| `get_secret` | `_homelab_bridge_common` |
| `docker_critical`, `docker_never_restart` | `_homelab_bridge_common` |
| `record_heartbeat` | `_homelab_bridge_heartbeat` |
| `ha_checks`, `ha_history`, `ha_check_status`, `ha_recorder_corrupt_files` | local, sin cambios (exclusivas — usan el propio handle `_ha_monitor` de este fichero, que sigue importándose aquí) |

## `src/inventory/_homelab_bridge.py` (fachada, más corto)

| Público (reexportado) | De dónde |
|---|---|
| `get_secret`, `telegram_credentials` | `_homelab_bridge_common` |
| `docker_critical`, `docker_never_restart` | `_homelab_bridge_common` |
| `record_heartbeat` | `_homelab_bridge_heartbeat` |
| `read_heartbeat` | local, sin cambios (exclusiva — usa el handle `_heartbeat` importado de `_homelab_bridge_heartbeat`, no uno propio) |
| `available()` | local, sin cambios (exclusiva — comprueba `_homelab_secrets`/`_heartbeat`, ambos handles importados) |
| `ha_monitor_checked_entities`, `ha_monitor_conditional_entities`, `ha_monitor_check_result` | local, sin cambios (exclusivas — usan el propio handle `_ha_monitor` de este fichero) |

## `src/remediacion/_homelab_bridge.py` (fachada, más corto)

| Público | De dónde |
|---|---|
| `telegram_credentials`, `docker_never_restart` | reexportadas tal cual de `_homelab_bridge_common` |
| `docker_critical` | **función local** que envuelve `_homelab_bridge_common.docker_critical()` y añade `REMEDIACION_TEST_FORZAR_CRITICO` (research.md §3) — nunca se reexporta la base tal cual |
| `listar_contenedores`, `restart_container`, `breaker_decision`, `recent_restart_attempts`, `declarar_correccion_ia` | local, sin cambios (exclusivas) |

`get_secret` no se reexporta aquí — `remediacion` nunca la ha usado
(solo `telegram_credentials`); añadirla sería alcance no pedido.

## Consumidores — qué deben seguir viendo tras el cambio

Ningún consumidor cambia una línea. Los 12 puntos de llamada
(`bridge.<función>(...)`) en `diagnostico/deepseek.py`,
`diagnostico/evidencia/{contenedor,ha}.py`, `inventory/{sources,evaluate,deliver}.py`,
`remediacion/{acciones,store,cli}.py` siguen accediendo por atributo
del módulo `_homelab_bridge` de su propio paquete — nunca directamente
a los módulos compartidos nuevos.
