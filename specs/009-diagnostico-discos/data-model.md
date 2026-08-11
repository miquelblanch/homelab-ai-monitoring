# Data Model — Generalizar el Diagnóstico a Discos

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-diagnostico-episodios/data-model.md`
— no lo sustituye. Solo se documentan aquí los campos que cambian.

## Episodio (generalizado)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | **Nuevo.** `"contenedor"` o `"disco"`. Migración: `DEFAULT 'contenedor'` para las 14 filas ya existentes (research.md §1). |
| `componente` | TEXT | **Renombrado** de `contenedor` (research.md §1) — nombre del contenedor si `origen='contenedor'`, `label` del disco (`"FastData"`/`"Storage"`/`"Sistema"`, research.md §2) si `origen='disco'`. |
| `es_critico` | INTEGER (bool) | Sin cambios de tipo. Para `origen='disco'`, siempre `False` (research.md §4) — no existe concepto de "disco crítico". |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--vivo`/`--disco-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='disco'` (no hay tabla de eventos discretos de disco, spec.md Assumptions). |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Sin cambios de forma — para disco, la ventana viene de `disk_metrics` en vez de `container_metrics` (research.md §3). |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='disco'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de disco (`snapshot_evidencia`, JSON)

```json
{
  "disco": {"label": "FastData", "path": "/Volumes/FastData"},
  "disk_metrics": [
    {"timestamp": "...", "used_percent": 0.0, "free_gb": 0.0}
  ],
  "restart_history": null,
  "container_metrics": null,
  "container_metrics_hourly": null,
  "docker_inspect": null,
  "docker_logs_tail": null
}
```

Los campos heredados de la forma de contenedor (`restart_history`,
`container_metrics`, `container_metrics_hourly`, `docker_inspect`,
`docker_logs_tail`) se mantienen presentes con valor `null` en un
episodio de disco — mismo criterio que ya aplica al revés en un
episodio de contenedor en vivo (`restart_history: null`,
`docker_inspect`/`docker_logs_tail` ausentes en uno histórico) — un
consumidor del snapshot nunca tiene que comprobar si una clave existe,
solo si es `null`.

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio
(`diagnostico_id`/`episodio_id` son claves foráneas por `id`, no
dependen de si el episodio es de contenedor o de disco).

## Esquema SQLite (cambios sobre `specs/007-.../data-model.md`)

```sql
-- Migración idempotente (research.md §1), no una tabla nueva:
ALTER TABLE episodios RENAME COLUMN contenedor TO componente;
ALTER TABLE episodios ADD COLUMN origen TEXT NOT NULL DEFAULT 'contenedor';
```

El resto del esquema (`diagnosticos`, `hipotesis`, `gasto_diario`) no
cambia.
