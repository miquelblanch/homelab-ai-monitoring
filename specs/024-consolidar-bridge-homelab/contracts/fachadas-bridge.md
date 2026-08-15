# Contrato: las tres fachadas `_homelab_bridge`

Igual que en 023: el contrato real es interno. Los consumidores de
producción deben poder seguir escribiendo `from . import
_homelab_bridge as bridge` (o `from .. import` desde `evidencia/`) y
`bridge.<función>(...)` exactamente como hoy — mismo nombre, misma
firma, mismo tipo de retorno.

## Firmas que las tres fachadas DEBEN preservar

| Paquete | Función | Firma | Origen tras el refactor |
|---|---|---|---|
| diagnostico | `get_secret(key: str, default: str = "") -> str` | sin cambios | `_homelab_bridge_common` |
| diagnostico | `record_heartbeat(job: str, status: str = "ok", detail: str = "") -> bool \| None` | sin cambios | `_homelab_bridge_heartbeat` |
| diagnostico | `docker_critical() -> set[str]` | sin cambios | `_homelab_bridge_common` |
| diagnostico | `docker_never_restart() -> set[str]` | sin cambios | `_homelab_bridge_common` |
| diagnostico | `ha_checks() -> list[dict]` | sin cambios | local (sin tocar) |
| diagnostico | `ha_history(entity_id, inicio_iso, fin_iso) -> list[dict] \| None` | sin cambios | local (sin tocar) |
| diagnostico | `ha_check_status(check: dict) -> dict \| None` | sin cambios | local (sin tocar) |
| diagnostico | `ha_recorder_corrupt_files(contenedor, ruta) -> list[str]` | sin cambios | local (sin tocar) |
| inventory | `get_secret(key, default="") -> str` | sin cambios | `_homelab_bridge_common` |
| inventory | `telegram_credentials() -> tuple[str, str]` | sin cambios | `_homelab_bridge_common` |
| inventory | `record_heartbeat(job, status="ok", detail="") -> bool \| None` | sin cambios | `_homelab_bridge_heartbeat` |
| inventory | `read_heartbeat(job) -> dict \| None` | sin cambios | local (usa handle importado) |
| inventory | `docker_critical() -> set[str]` | sin cambios | `_homelab_bridge_common` |
| inventory | `docker_never_restart() -> set[str]` | sin cambios | `_homelab_bridge_common` |
| inventory | `available() -> bool` | sin cambios | local (usa handles importados) |
| inventory | `ha_monitor_checked_entities() -> set[str]` | sin cambios | local (sin tocar) |
| inventory | `ha_monitor_conditional_entities() -> set[str]` | sin cambios | local (sin tocar) |
| inventory | `ha_monitor_check_result(entity_id) -> dict \| None` | sin cambios | local (sin tocar) |
| remediacion | `telegram_credentials() -> tuple[str, str]` | sin cambios | `_homelab_bridge_common` |
| remediacion | `docker_never_restart() -> set[str]` | sin cambios | `_homelab_bridge_common` |
| remediacion | `docker_critical() -> set[str]` | sin cambios en firma; implementación pasa a envolver la base compartida + hook de test | **local**, nunca reexportada tal cual (FR-003) |
| remediacion | `listar_contenedores() -> list[dict]` | sin cambios | local (sin tocar) |
| remediacion | `restart_container(name, reason="") -> bool` | sin cambios | local (sin tocar) |
| remediacion | `breaker_decision(attempts, max_attempts=3) -> tuple[bool, str]` | sin cambios | local (sin tocar) |
| remediacion | `recent_restart_attempts(conn_remediacion, contenedor, window_hours=6) -> int` | sin cambios | local (sin tocar) |
| remediacion | `declarar_correccion_ia(origen, tipo, componente, nota) -> bool` | sin cambios | local (sin tocar) |

Todas las firmas están copiadas literalmente de los tres ficheros
actuales, no reconstruidas de memoria.

## Cómo se verifica el contrato (para `tasks.md`)

1. **Import**: `from diagnostico import _homelab_bridge as bridge` (y
   equivalentes en inventory/remediacion) sigue funcionando, y cada
   nombre de la tabla resuelve a una función con la misma firma
   (`inspect.signature` antes/después).
2. **Comportamiento**: la suite de tests existente
   (`test_remediacion_cli.py`, `test_remediacion_acciones.py`,
   `test_evaluate.py`, `test_evidencia_contenedor.py`,
   `test_evidencia_ha.py`, y el resto de `--selftest`) sigue en verde
   con el mismo recuento — sin reescribir ningún test (research.md §2).
3. **Aislamiento del hook de prueba**: `docker_critical` de
   diagnostico e inventory nunca responde a
   `REMEDIACION_TEST_FORZAR_CRITICO` — verificable poniendo esa
   variable de entorno y comprobando que `diagnostico._homelab_bridge.docker_critical()`
   e `inventory._homelab_bridge.docker_critical()` no cambian de
   resultado, mientras que `remediacion._homelab_bridge.docker_critical()` sí.
