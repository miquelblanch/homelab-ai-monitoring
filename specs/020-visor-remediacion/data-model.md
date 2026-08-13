# Data Model — Visor de Remediación en el Dashboard

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

## Snapshot de remediación (`remediacion_estado.json`)

| Campo | Tipo | Notas |
|---|---|---|
| `generado_en` | string (ISO 8601) | Momento de la última ejecución de `comprobar` — siempre visible en el dashboard (FR-002). |
| `modo_rotar_log` | `"manual"` \| `"automatico"` | El modo vigente en el momento de generar el snapshot. |
| `logs` | lista de objetos | Uno por cada entrada de `LOGS_VIGILADOS` (17 hoy). |
| `logs[].nombre` | string | Nombre corto (`"health-docker"`, `"dashboard-socat"`...). |
| `logs[].tamano_bytes` | integer | `0` si el fichero no existe en el momento de comprobar (spec.md Edge Cases). |
| `logs[].umbral_bytes` | integer | El umbral configurado para ese log. |
| `logs[].supera_umbral` | boolean | `tamano_bytes > umbral_bytes`. |

## Funciones nuevas (`src/remediacion/acciones.py`)

| Función | Uso |
|---|---|
| `escribir_snapshot(conn)` | Recorre `LOGS_VIGILADOS`, arma el JSON de arriba con `get_modo(conn, "rotar_log")` y los tamaños reales, y lo escribe en `REMEDIACION_SNAPSHOT_PATH`. Nunca lanza — un fallo de escritura no debe tumbar `comprobar` (mismo principio a prueba de fallos que el resto del homelab). |

## Constante nueva

| Constante | Valor | Uso |
|---|---|---|
| `REMEDIACION_SNAPSHOT_PATH` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json`, configurable | Ruta del snapshot — mismo directorio que `diagnostico.db` (research.md §2). |

## Fuera de este repo

| Pieza | Notas |
|---|---|
| `get_remediacion_estado()` (`app.py`) | Lee `remediacion_estado.json` con `mode=ro`-style try/except — `None` si no existe o falla (research.md §4). |
| Sección HTML/JS nueva | Dentro del panel `sistema` — nombre, tamaño, umbral, marca visual si `supera_umbral`, y `modo_rotar_log` — sin ningún control interactivo (FR-006). |
| `amsterdam9.remediacion.comprobar.plist` | LaunchAgent nuevo, `StartInterval=900` (research.md §3). |
