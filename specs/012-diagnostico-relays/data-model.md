# Data Model — Generalizar el Diagnóstico a los Relays

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009/010/011 — no lo sustituye. Solo se documentan aquí
los campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Quinto valor real: `"relay"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | **Asimétrico por diseño** (research.md §2): en vivo, el nombre del relay (`"Beszel AdGuard"`); en diferido, el momento ISO pedido — sin ningún nombre de relay, porque no hay ninguno que identificar. |
| `es_critico` | INTEGER (bool) | Siempre `False` para `origen='relay'` — no existe concepto de "relay crítico". |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--relay-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='relay'`. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | En vivo, ambas coinciden con el instante de congelar. En diferido, `[momento - VENTANA_RELAY_MINUTOS, momento + VENTANA_RELAY_MINUTOS]` (±180 min, research.md §5). |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='relay'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de relay (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores (`disco`, `restart_history`,
`container_metrics*`, `disk_metrics`, `docker_inspect`,
`docker_logs_tail`, `ha_*`, `backup_*`) se mantienen presentes con
valor `null` en un episodio de relay. Se añaden tres claves nuevas:

```json
{
  "...": "(resto de campos heredados a null)",
  "relay_nombre": "Beszel AdGuard",
  "relay_estado_actual": {
    "name": "Beszel AdGuard",
    "desc": "192.168.4.87:45877 → 192.168.4.174:45876",
    "ok": true
  },
  "relay_agregado": null
}
```

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `relay_nombre` | Episodio en vivo | El nombre pedido, tal cual — `null` en diferido (research.md §2). |
| `relay_estado_actual` | Episodio en vivo, y el nombre existe en `socat_relays.json` | `{name, desc, ok}` tal cual esa entrada — **`desc` incluye IPs reales de la LAN, enviadas con justificación explícita** (research.md §4). `null` si el nombre no existe (spec.md Edge Cases) o en diferido. |
| `relay_agregado` | Episodio en diferido | Lista de `{momento, ok, total}` — una entrada por línea de `dashboard-socat.log` dentro de la ventana de ±180 min, acotada a `RELAY_AGREGADO_MAX_LINEAS` (100, research.md §5). `[]` si no hay ninguna línea en la ventana; `null` en vivo. **Nunca identifica qué relay concreto** — esa información no existe para episodios pasados (spec.md FR-006). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/011-.../data-model.md` — ninguna
migración nueva (research.md §1).

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `SOCAT_RELAYS_JSON` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json` (configurable) | Fuente de evidencia en vivo (research.md §3). |
| `DASHBOARD_SOCAT_LOG` | `~/Library/Logs/dashboard-socat.log` (configurable, expandido con `Path.expanduser()`) | Fuente de evidencia en diferido — primer fichero fuera de `/Volumes/FastData/homelab/` (research.md §5). |
| `VENTANA_RELAY_MINUTOS` | `180` | Ventana ± minutos alrededor del momento pedido en diferido (research.md §5). |
| `RELAY_AGREGADO_MAX_LINEAS` | `100` | Límite defensivo, no motivado por un caso real como en 010/011 — la ventana ya acota a ~72 líneas por diseño (research.md §5). |
