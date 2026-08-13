# Data Model — Generalizar el Diagnóstico a los Latidos de Monitores

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009-016 — no lo sustituye. Solo se documentan aquí los
campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Décimo y último valor real: `"latido"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | El `job` pedido (uno de los 8 de `MONITOR_JOBS`). |
| `es_critico` | INTEGER (bool) | Siempre `False`. |
| `en_vivo` | INTEGER (bool) | **Siempre `True`** para este origen — no existe `en_vivo=False` (research.md §2). |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Ambas coinciden siempre con el instante de congelar — no hay modo diferido con una ventana distinta. |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='latido'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de latido (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores se mantienen presentes con
valor `null`. Se añade una clave nueva:

```json
{
  "...": "(resto de campos heredados a null)",
  "latido_actual": {
    "job": "docker-monitor",
    "label": "Monitor de Docker",
    "detail": "40 contenedores",
    "status": "ok",
    "ok": true,
    "age_s": 312.4,
    "max_age_s": 1800
  }
}
```

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `latido_actual` | Siempre que `job` está entre los 8 de `MONITOR_JOBS` | `{job, label, detail, status, ok, age_s, max_age_s}` — `ok` calculado únicamente por edad, igual que `app.py::get_monitor_heartbeats()` (research.md §3, **nunca combinado con `status`** — hallazgo real de §3). Si el fichero `<job>.json` no existe todavía, o cualquier lectura falla, `age_s`/`status` son `null`, `ok` es `false` y `detail` es `"sin latido"` — mismo texto exacto que usa `app.py::get_monitor_heartbeats()` para cualquier excepción (research.md §3). `null` entero si `job` no está entre los 8 (spec.md Edge Cases). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/016-.../data-model.md` — ninguna
migración nueva (research.md §1).

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `MONITOR_HEARTBEATS_DIR` | `/Volumes/FastData/homelab/data/heartbeats` (configurable) | Directorio con un `<job>.json` por job — mismo que lee `app.py::get_monitor_heartbeats()` (research.md §2/§3). |
| `MONITOR_JOBS` | Lista de 8 `(job, label, max_age_s)`, copia literal de `app.py::MONITOR_JOBS` | Universo cerrado de jobs diagnosticables — un `job` fuera de esta lista es "no se puede diagnosticar", no un error (research.md §3, Assumptions de spec.md). |

## Funciones nuevas (`evidencia.py`)

| Función | Uso |
|---|---|
| `_latido_actual(job)` | Busca `job` en `MONITOR_JOBS`, lee su `<job>.json`, calcula `ok` únicamente por edad (research.md §3). |
| `congelar_latido_vivo(conn, job)` | Único constructor de episodio de este origen — no existe `congelar_latido_historico` (research.md §2). |
