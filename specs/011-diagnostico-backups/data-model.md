# Data Model — Generalizar el Diagnóstico a los Backups

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de
`specs/007-diagnostico-episodios/data-model.md`, extendido por
`specs/009-diagnostico-discos/data-model.md` y
`specs/010-diagnostico-ha/data-model.md` — no lo sustituye. Solo se
documentan aquí los campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Cuarto valor real: `"backup"` (además de `"contenedor"`/`"disco"`/`"ha"`). **Sin migración** — la columna ya es TEXT libre desde 009 (research.md §1 de 011). |
| `componente` | TEXT | Para `origen='backup'`: el momento de la ejecución en ISO 8601, tomado del nombre del fichero de log (`backup_YYYY-MM-DD_HH-MM-SS.log`) — no hay ningún nombre de componente que elegir, solo existe una serie (research.md §2 de 011). |
| `es_critico` | INTEGER (bool) | Para `origen='backup'`, siempre `False` — no existe concepto de "backup crítico" (research.md §7 de 011). |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--backup-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='backup'`. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Para backup, ambas coinciden con el momento de la ejecución tal cual aparece en el nombre del log — no hay una ventana temporal que ampliar alrededor, el log ya es la unidad completa de esa ejecución. |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='backup'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de backup (`snapshot_evidencia`, JSON)

Los ocho campos ya existentes de orígenes anteriores (`disco`,
`restart_history`, `container_metrics`, `container_metrics_hourly`,
`disk_metrics`, `docker_inspect`, `docker_logs_tail`, `ha_check`,
`ha_check_status`, `ha_history`, `ha_recorder_corrupt_files`) se
mantienen presentes con valor `null` en un episodio de backup — mismo
criterio ya establecido en 007/009/010. Se añaden cinco claves nuevas,
ninguna reutilizada de un origen anterior (la forma de la evidencia de
backup no se parece a la de ningún origen previo):

```json
{
  "disco": null,
  "restart_history": null,
  "container_metrics": null,
  "container_metrics_hourly": null,
  "disk_metrics": null,
  "docker_inspect": null,
  "docker_logs_tail": null,
  "ha_check": null,
  "ha_check_status": null,
  "ha_history": null,
  "ha_recorder_corrupt_files": null,
  "backup_log_path": "/Volumes/FastData/homelab/logs/backup_2026-08-12_02-00-00.log",
  "backup_dumps": ["✅ Nextcloud MariaDB dump OK", "✅ Immich PostgreSQL dump OK", "..."],
  "backup_rsync_stats": ["Number of files: 1,101,900 ...", "Total transferred file size: 21.77G bytes", "..."],
  "backup_resumen_final": "Duración 17m 36s — rsync completo",
  "backup_rsync_estado": "ok",
  "backup_anomalias": []
}
```

| Clave nueva | Contenido |
|---|---|
| `backup_log_path` | Ruta del fichero de log del que se congeló la evidencia — para poder ir a leerlo entero a mano si hace falta, sin que el propio motor lo cargue nunca completo (research.md §3 de 011). |
| `backup_dumps` | Líneas de estado de cada dump de base de datos (`✅`/`⚠️`), tal cual aparecen en el log. |
| `backup_rsync_stats` | El bloque `--stats` de rsync — tamaño fijo, independiente de cuántos ficheros cambiaran esa noche. |
| `backup_resumen_final` | La línea `RESUMEN FINAL` completa (duración + código de rsync ya interpretado). |
| `backup_rsync_estado` | `"ok"` o `"error"` — mismo valor que ya calcula `RSYNC_ESTADO` dentro de `backup_diario_nvme.sh`, solo parseado del log, no recalculado. |
| `backup_anomalias` | Hasta `BACKUP_ANOMALIA_MAX_LINEAS` (30) líneas que coinciden con patrones de error real de rsync en cualquier punto del log, **excluidas las que ya aparecen en `backup_dumps`** (research.md §3, hallazgo I1 de `/speckit-analyze`) — `[]` si no hay ninguna, nunca `null` (el log siempre se llega a leer si el fichero existe). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios respecto a `specs/010-.../data-model.md`** — ninguna
migración nueva (research.md §1 de 011).

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `BACKUP_LOG_DIR` | `/Volumes/FastData/homelab/logs` (configurable vía `BACKUP_LOG_DIR`) | Directorio donde buscar `backup_*.log`. |
| `VENTANA_BACKUP_HORAS` | `12` | Tolerancia para encontrar el log más cercano a un `MOMENTO_ISO` en `--backup-historico` (research.md §5 de 011). |
| `BACKUP_ANOMALIA_MAX_LINEAS` | `30` | Límite de líneas de anomalía extraídas del log (research.md §3 de 011). |
