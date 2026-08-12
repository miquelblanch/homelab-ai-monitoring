# Data Model — Generalizar el Diagnóstico al Inventario de Cobertura

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009/010/011/012 — no lo sustituye. Solo se documentan
aquí los campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Sexto valor real: `"inventario"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | El `nombre_actual` del componente — **simétrico en vivo y en diferido** (research.md §3), a diferencia de relays. En diferido, la `EJECUCION_ID` pedida vive en el snapshot (`inventario_ejecucion_id`), no aquí. |
| `es_critico` | INTEGER (bool) | Siempre `False` para `origen='inventario'` — no existe concepto de "componente crítico". |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--inventario-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='inventario'`. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Ambas iguales a la fecha real de la ejecución consultada (`ejecuciones.fecha`) — o al momento de invocar `congelar` si esa ejecución no existe (research.md §9). |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='inventario'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de inventario (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores (`disco`, `restart_history`,
`container_metrics*`, `disk_metrics`, `docker_inspect`,
`docker_logs_tail`, `ha_*`, `backup_*`, `relay_*`) se mantienen
presentes con valor `null` en un episodio de inventario. Se añaden
cuatro claves nuevas:

```json
{
  "...": "(resto de campos heredados a null)",
  "inventario_ejecucion_id": 19,
  "inventario_hallazgo": {
    "categoria": "hermes",
    "nombre_actual": "Agente Hermes/Bautista",
    "tiene_estado_declarado": true,
    "estado_declarado_status": "vigente",
    "esta_vigilado": true,
    "mecanismo_vigilancia": "amsterdam9.bautista.heartbeat",
    "llega_a_dashboard": "no",
    "es_brecha": true
  },
  "inventario_brecha": {
    "tipo": "no_llega_a_dashboard",
    "contexto": "'Agente Hermes/Bautista' (hermes) está vigilado por amsterdam9.bautista.heartbeat, pero un fallo real no llegaría al dashboard del homelab.",
    "primera_ejecucion_id": 19,
    "conocida_por_barrido_previo": null
  },
  "inventario_comparacion": {
    "ejecucion_actual_id": 19,
    "ejecucion_previa_id": 2,
    "componentes_nuevos": {"total": 3, "muestra": ["..."]},
    "componentes_de_baja": {"total": 0, "muestra": []},
    "brechas_nuevas": {"total": 319, "muestra": ["Agente Hermes/Bautista", "..."]},
    "brechas_resueltas": {"total": 0, "muestra": []}
  }
}
```

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `inventario_ejecucion_id` | Siempre que se pide un episodio de inventario | La ejecución consultada — la más reciente en vivo, o la pedida en diferido (research.md §3). |
| `inventario_hallazgo` | El componente `nombre_actual` existe en esa ejecución | Fila de `hallazgos` (con `categoria`/`nombre_actual` ya unidos vía `inventory.store.hallazgos_de_ejecucion`) — `null` si el nombre no aparece en esa ejecución (spec.md Edge Cases). |
| `inventario_brecha` | El hallazgo es una brecha de uno de los 5 tipos en alcance | Fila de `brechas` — `null` si el componente no tiene brecha activa en esa ejecución (research.md §9). Nunca de tipo `condicion_incumplida`: esa combinación se rechaza antes de llegar aquí (FR-010, research.md §5). |
| `inventario_comparacion` | `inventario_brecha` no es `null` y `primera_ejecucion_id > 1` | El resultado de `inventory.diff.compare_runs()` contra `primera_ejecucion_id - 1` — **no** contra `ejecucion_id - 1` (research.md §4). `null` si no hay brecha o si `primera_ejecucion_id == 1`. Cada una de las cuatro listas va acotada a `{"total": N, "muestra": lista[:30]}` — el caso real más grande medido llega a 319 (research.md §11). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/012-.../data-model.md` — ninguna
migración nueva (research.md §1). `inventario.db` tampoco cambia de
esquema — este feature solo lo lee a través de `inventory.store`
(research.md §2).

## Funciones nuevas (`evidencia.py`)

| Función | Uso |
|---|---|
| `_hallazgo_de_componente(conn_inv, ejecucion_id, nombre)` | Busca `nombre` entre `inventory.store.hallazgos_de_ejecucion()` de esa ejecución (research.md §4). |
| `_brecha_de_componente(conn_inv, ejecucion_id, nombre)` | Busca `nombre` entre `inventory.store.brechas_de_ejecucion()` de esa ejecución — **sin filtrar por tipo**, devuelve cualquiera de los 6 tipos posibles si existe. El rechazo de `condicion_incumplida` es responsabilidad exclusiva de `_validar_tipo_brecha_inventario()` (research.md §4/§5) — filtrar aquí dejaría esa comprobación sin nada que rechazar. |
| `_validar_tipo_brecha_inventario(brecha)` | Lanza `ValueError` si `brecha["tipo"] == "condicion_incumplida"` — antes de congelar nada (FR-010, research.md §5). |
| `_comparacion_dict(comparacion)` | Envuelve cada lista de `inventory.diff.Comparacion` en `{"total", "muestra"}`, acotada a `INVENTARIO_COMPARACION_MAX_ENTRADAS` (research.md §11). |
| `congelar_inventario_vivo(conn, nombre)` | Ejecución = la más reciente de `inventario.db` (research.md §3). |
| `congelar_inventario_historico(conn, nombre, ejecucion_id)` | Ejecución = la pedida explícitamente (research.md §3/§9). |

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `INVENTARIO_COMPARACION_MAX_ENTRADAS` | `30` | Límite por lista dentro de `inventario_comparacion` — el caso real más grande medido llega a 319 (research.md §11). |
