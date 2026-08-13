# Research — Visor de Remediación en el Dashboard

**Feature**: [spec.md](./spec.md)

## §1 — El contenedor no monta `~/Library/Logs`: JSON a `/data`, no un volumen nuevo

**Hallazgo real**, comprobado en `docker-compose.yml` de
`homelab-dashboard` antes de diseñar nada:

```yaml
volumes:
  - /Volumes/FastData/homelab/docker/homelab-orchestrator/data:/data
  - /Users/miquelblanch/.hermes:/root/.hermes:ro
  - /Volumes/FastData:/Volumes/FastData:ro
  - /Volumes/Storage:/Volumes/Storage:ro
```

`~/Library/Logs/` (donde viven los 17 logs vigilados) no está montado
— nunca lo ha estado. Añadirlo exigiría editar `docker-compose.yml` y
**recrear** el contenedor (no solo reconstruir la imagen), la primera
vez que se tocaría ese volumen.

**Decisión, confirmada con Miquel (`AskUserQuestion`, 2026-08-13)**:
mismo patrón ya usado en todo el homelab
(`dump_socat_status.py`→`socat_relays.json`,
`beszel_hosts_monitor.py`→`beszel_hosts.json`) — un proceso en el host
escribe un JSON a `/data` (ya montado), el dashboard solo lee. Cero
cambios de infraestructura del contenedor.

## §2 — `escribir_snapshot()`: parte de `comprobar`, no un comando aparte

**Decisión**: `remediacion.cli comprobar` ya recorre `LOGS_VIGILADOS`
calculando tamaño real de cada uno (`acciones.comprobar_rotar_log()`,
019) — añadir la escritura del snapshot ahí es la opción más simple,
sin duplicar la lógica de recorrido. Forma del JSON:

```json
{
  "generado_en": "2026-08-13T18:30:00+00:00",
  "modo_rotar_log": "manual",
  "logs": [
    {"nombre": "health-docker", "tamano_bytes": 5032, "umbral_bytes": 10485760, "supera_umbral": false},
    {"nombre": "dashboard-socat", "tamano_bytes": 1778290, "umbral_bytes": 10485760, "supera_umbral": false}
  ]
}
```

Ruta: `REMEDIACION_SNAPSHOT_PATH`, configurable, por defecto
`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json`
— mismo directorio que `diagnostico.db`/`socat_relays.json`.

## §3 — Cadencia: LaunchAgent nuevo cada 15 min, sin cambiar el modo por defecto

**Decisión**: `amsterdam9.remediacion.comprobar`, `StartInterval` de
900 s (15 min) — misma cadencia que `ha_monitor.py`. Ejecuta
`PYTHONPATH=.../src python3 -m remediacion.cli comprobar`. No cambia
ninguna decisión ya tomada en 019: `rotar_log` sigue empezando en
modo manual; si Miquel lo pone en automático, es este mismo cron el
que dispara la ejecución real cada 15 min — coherente con lo que ya
significa "modo automático" (research.md §1 de 019), no un mecanismo
nuevo.

## §4 — Sección nueva en el dashboard: lectura, dentro de "Sistema & almacenamiento"

**Decisión**: `get_remediacion_estado()` en `app.py`, mismo patrón
`try/except` a prueba de fallos que el resto de colectores (FR-007) —
`None`/vacío si el JSON no existe o no se puede leer, nunca rompe el
resto de `/api/data`. Se añade como sub-bloque dentro del panel ya
existente "Sistema & almacenamiento" (id `sistema`, visible por
defecto) — encaja como housekeeping de disco/logs, sin crear una
pestaña nueva para una única lista de 17 filas. Sin ningún botón ni
control — FR-006, verificado por inspección del HTML/JS (SC-004).

## §9 — Dos totales, pedidos por Miquel tras ver la lista completa

**Decisión**: además de la fila por log, `escribir_snapshot()` calcula
dos totales agregados —`total_activos_bytes` (suma de los 17 ficheros
activos) y `total_con_rotaciones_bytes` (activos + todas sus
rotaciones `.rotado-*` archivadas, research.md §8 de 019)— para que
Miquel vea de un vistazo cuánto ocupa todo junto, sin sumar fila a
fila. El dashboard los muestra en la cabecera de la sección, no como
filas nuevas de la tabla.
