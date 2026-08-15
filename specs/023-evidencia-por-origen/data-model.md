# Phase 1 — Data Model: Evidencia de Diagnóstico Organizada por Origen

No hay un modelo de datos nuevo — `Episodio` (`diagnostico/model.py`) y su
persistencia (`diagnostico/store.py`) no cambian. Lo que este documento
mapea es la partición real de `evidencia.py` en las entidades que ya
describe `spec.md` (Origen de evidencia, Mecanismo compartido, Consumidor),
con el inventario exacto de qué función va a cada módulo — verificado por
uso real (`research.md` §2), no por el nombre de la función ni por su
posición actual en el fichero.

## Mecanismo compartido → `_compartido.py`

| Elemento | Motivo |
|---|---|
| `homelab_db_path()` | conexión a `homelab.db`, usada por contenedor y disco |
| `_connect_homelab_db()` | ídem |
| `_run_ro()` | primitiva de subproceso de solo lectura, base de `docker_logs_tail` |
| `docker_logs_tail()` | usada por contenedor y ha |
| `_docker_bin()` | usada por host_externo y hub_beszel |
| `BESZEL_HUB_VOLUME` | ídem — mismo volumen Docker, dos orígenes |

`insert_episodio` sigue en `store.py`, ya extraída de `evidencia.py` desde
antes de esta feature — no se mueve.

## Origen de evidencia → un módulo por origen

Cada fila es un origen tal como lo define `spec.md` (Key Entities). La
columna "Solo suyo" es lo que hoy parece compartido por el nombre o la
posición en el fichero pero el uso real (`research.md` §2) descarta —
para que `tasks.md` no repita el error de moverlo a `_compartido.py`.

| Origen | Módulo | Público (reexportado por la fachada) | Privado (solo test de origen) | Solo suyo, aunque no lo parezca |
|---|---|---|---|---|
| Contenedor | `contenedor.py` | `congelar_historico`, `congelar_vivo` | — | `restart_history_row`, `container_metrics_window`, `container_metrics_hourly_window`, `container_metrics_recientes`, `disk_metrics_near`, `docker_inspect`, `_parse_docker_inspect`, `es_critico` |
| Disco | `disco.py` | `congelar_disco_vivo`, `congelar_disco_historico` | `disk_metrics_window`, `disk_metrics_recientes`, `_disco_path` | — |
| Home Assistant | `ha.py` | `congelar_ha_vivo`, `congelar_ha_historico` | `ha_check_by_id`, `_simplificar_historial`, `ha_history_window`, `_validar_check_ha`, `_resolver_evidencia_ha` | `CHECKS_HA_EXCLUIDOS_CERRADURA` (constante, no función — sigue siendo solo de ha) |
| Backup | `backup.py` | `congelar_backup_vivo`, `congelar_backup_historico` | `_listar_logs_backup`, `_momento_de_log_backup`, `_log_backup_mas_reciente`, `_log_backup_cercano`, `_parsear_log_backup`, `_snapshot_backup_vacio`, `_congelar_backup` | — |
| Relay | `relay.py` | `congelar_relay_vivo`, `congelar_relay_historico`, `listar_nombres_relay`, `nombres_relay_evidenciados` (estas dos también reexportadas — las usa `deepseek.py`) | `_relay_actual`, `_agregado_relays_ventana`, `_snapshot_relay_vacio` | — |
| Inventario | `inventario.py` | `congelar_inventario_vivo`, `congelar_inventario_historico` | `_hallazgo_de_componente`, `_brecha_de_componente`, `_validar_tipo_brecha_inventario`, `_comparacion_dict`, `_snapshot_inventario_vacio`, `_armar_episodio_inventario` | importa `inv_diff`, `inv_store`, `TIPOS_BRECHA` de `inventory` — solo aquí |
| Host externo | `host_externo.py` | `congelar_host_externo_vivo`, `congelar_host_externo_historico` | `_a_utc_madrid`, `_host_externo_actual`, `_consultar_beszel_hub`, `_resumen_system_stats`, `_snapshot_host_externo_vacio`, `_QUERY_SYSTEM_STATS` | — |
| Hub Beszel | `hub_beszel.py` | `congelar_hub_beszel_vivo`, `congelar_hub_beszel_historico` | `_hub_beszel_actual`, `_consultar_beszel_hub_todos_sistemas`, `_resumen_por_sistema`, `_snapshot_hub_beszel_vacio`, `_QUERY_SYSTEM_STATS_TODOS` | — |
| Agente | `agente.py` | `congelar_agente_vivo` (sin variante histórica — no existe evidencia real pasada para LaunchAgents, spec Edge Cases) | `_agente_actual`, `_snapshot_agente_vacio` | — |
| Latido | `latido.py` | `congelar_latido_vivo` (sin variante histórica — mismo motivo que agente) | `_latido_actual`, `_snapshot_latido_vacio` | — |

## Consumidor → qué debe seguir viendo cada uno tras el cambio

| Consumidor | Fichero | Sigue llamando (sin cambios) |
|---|---|---|
| Dispatch por episodio | `diagnostico/cli.py` | `evidencia.congelar_<origen>_vivo` / `_historico` de los diez orígenes (18 llamadas) |
| Remediación de contenedores | `remediacion/acciones.py:518` | `evidencia.congelar_vivo` |
| Validación de hipótesis (relay) | `diagnostico/deepseek.py:388-391` | `evidencia.nombres_relay_evidenciados`, `evidencia.listar_nombres_relay` |

## `evidencia/__init__.py` — superficie exacta de la fachada

Solo lo que la tabla de Consumidor de arriba usa de verdad — no todo lo
público de cada origen, y desde luego nada de lo marcado "Privado":

```python
from .contenedor import congelar_historico, congelar_vivo
from .disco import congelar_disco_vivo, congelar_disco_historico
from .ha import congelar_ha_vivo, congelar_ha_historico
from .backup import congelar_backup_vivo, congelar_backup_historico
from .relay import (
    congelar_relay_vivo, congelar_relay_historico,
    listar_nombres_relay, nombres_relay_evidenciados,
)
from .inventario import congelar_inventario_vivo, congelar_inventario_historico
from .host_externo import congelar_host_externo_vivo, congelar_host_externo_historico
from .hub_beszel import congelar_hub_beszel_vivo, congelar_hub_beszel_historico
from .agente import congelar_agente_vivo
from .latido import congelar_latido_vivo
```

Nada más se reexporta. Cualquier otra función (privada o pública dentro de
un origen) se usa, desde fuera de su propio módulo, solo por su test de
origen correspondiente — nunca por otro origen ni por un consumidor.
