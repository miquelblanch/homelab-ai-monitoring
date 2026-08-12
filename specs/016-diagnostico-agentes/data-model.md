# Data Model — Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009-015 — no lo sustituye. Solo se documentan aquí los
campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Noveno y último valor real: `"agente"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | El `label` del agente pedido. |
| `es_critico` | INTEGER (bool) | Siempre `False`. |
| `en_vivo` | INTEGER (bool) | **Siempre `True`** para este origen — no existe `en_vivo=False` (research.md §2). |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Ambas coinciden siempre con el instante de congelar — no hay modo diferido con una ventana distinta. |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='agente'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de agente (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores se mantienen presentes con
valor `null`. Se añade una clave nueva:

```json
{
  "...": "(resto de campos heredados a null)",
  "agente_actual": {
    "label": "amsterdam9.morning-report",
    "pid": "-",
    "exit_code": "0",
    "running": false,
    "status": "idle"
  }
}
```

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `agente_actual` | Siempre que el `label` existe en `launchagents_raw.txt` | `{label, pid, exit_code, running, status}` — `status` ∈ `{"running", "idle", "error"}`, mismo cálculo que `app.py::get_launchagents()` (research.md §3). `null` si `label` no existe (spec.md Edge Cases). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/015-.../data-model.md` — ninguna
migración nueva (research.md §1).

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `LAUNCHAGENTS_RAW` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/launchagents_raw.txt` (configurable) | Única fuente de evidencia — sin par histórico (research.md §2/§3). |

## Funciones nuevas (`evidencia.py`)

| Función | Uso |
|---|---|
| `_agente_actual(label)` | Busca `label` en `LAUNCHAGENTS_RAW`, calcula `running`/`status` (research.md §3). |
| `congelar_agente_vivo(conn, label)` | Único constructor de episodio de este origen — no existe `congelar_agente_historico` (research.md §2). |
