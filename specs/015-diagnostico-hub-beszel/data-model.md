# Data Model — Generalizar el Diagnóstico al Hub de Beszel

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009-014 — no lo sustituye. Solo se documentan aquí los
campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Octavo valor real: `"hub_beszel"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | `momento.isoformat()` en ambos modos — **sin identificador**, igual que backup (research.md §2). |
| `es_critico` | INTEGER (bool) | Siempre `False`. |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--hub-beszel-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | En vivo, ambas coinciden con el instante de congelar. En diferido, `[momento - 1440min, momento + 1440min]` en hora local de Madrid. |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='hub_beszel'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio del hub (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores se mantienen presentes con
valor `null`. Se añaden dos claves nuevas:

```json
{
  "...": "(resto de campos heredados a null)",
  "hub_beszel_actual": {
    "systems": [
      {"name": "Mac Mini Server", "age_s": 120.4, "stale": false},
      {"name": "AdGuardHome", "age_s": 118.9, "stale": false},
      {"name": "UptimeKuma", "age_s": 121.2, "stale": false}
    ],
    "sano": true
  },
  "hub_beszel_stats": null
}
```

o, en diferido:

```json
{
  "...": "(resto de campos heredados a null)",
  "hub_beszel_actual": null,
  "hub_beszel_stats": {
    "por_sistema": {
      "Mac Mini Server": {"total_muestras": 6, "primera": "2026-08-02 00:20:00.031Z", "ultima": "2026-08-02 16:20:00.018Z", "por_tipo": {"120m": 6}},
      "AdGuardHome": {"total_muestras": 0, "primera": null, "ultima": null, "por_tipo": {}},
      "UptimeKuma": {"total_muestras": 0, "primera": null, "ultima": null, "por_tipo": {}}
    },
    "todos_sin_muestras": false
  }
}
```

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `hub_beszel_actual` | Episodio en vivo | `{systems: [{name, age_s, stale}], sano}` — mismo cálculo que `app.py::get_beszel_hub_status()` (research.md §3). `sano=False` si `systems` está vacío. `null` en diferido. |
| `hub_beszel_stats` | Episodio en diferido | `{por_sistema: {nombre: {total_muestras, primera, ultima, por_tipo}}, todos_sin_muestras}` (research.md §4/§5). `todos_sin_muestras` calculado en código, nunca inferido por el modelo. `null` en vivo, **y también** en diferido si la consulta al hub falló (research.md §7). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/014-.../data-model.md` — ninguna
migración nueva (research.md §1). El hub de Beszel tampoco cambia de
esquema — este feature solo lo consulta con `SELECT` parametrizado.

## Constantes (`evidencia.py`)

Reutilizadas tal cual de 014 (research.md §3/§4): `BESZEL_HOSTS_JSON`,
`BESZEL_HOSTS_MAX_AGE_S`, `BESZEL_HUB_VOLUME`, `_docker_bin()`,
`_a_utc_madrid()`, `_resumen_system_stats()`.

Nueva de este feature:

| Constante | Valor | Uso |
|---|---|---|
| `VENTANA_HUB_BESZEL_MINUTOS` | `1440` (±24h) | Ventana alrededor del momento pedido en diferido — misma justificación que `VENTANA_HOST_EXTERNO_MINUTOS` de 014 (research.md §10). |

## Funciones nuevas (`evidencia.py`)

| Función | Uso |
|---|---|
| `_hub_beszel_actual()` | Replica `get_beszel_hub_status()` — antigüedad de todos los sistemas + `sano` (research.md §3). |
| `_consultar_beszel_hub_todos_sistemas(inicio_utc, fin_utc)` | Generaliza `_consultar_beszel_hub()` de 014 — `LEFT JOIN` para no perder sistemas sin muestras (research.md §4). |
| `_resumen_por_sistema(filas)` | Agrupa por sistema y reutiliza `_resumen_system_stats()` de 014, calcula `todos_sin_muestras` (research.md §4/§5). |
| `congelar_hub_beszel_vivo(conn)` | Sin argumento — solo hay un hub (research.md §2). |
| `congelar_hub_beszel_historico(conn, momento)` | Sin nombre de componente (research.md §2/§9). |
