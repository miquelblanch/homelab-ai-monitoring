# Data Model — Generalizar el Diagnóstico a los Hosts Externos

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de `specs/007-.../data-model.md`,
extendido por 009-013 — no lo sustituye. Solo se documentan aquí los
campos que cambian.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Séptimo valor real: `"host_externo"`. **Sin migración** (research.md §1). |
| `componente` | TEXT | El nombre canónico del host (`"Host de Uptime Kuma"` o `"Host de AdGuard Home (DNS primario)"`) — **simétrico en vivo y en diferido** (research.md §2), como inventario. |
| `es_critico` | INTEGER (bool) | Siempre `False` — no existe concepto de "host crítico". |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--host-externo-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='host_externo'`. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | En vivo, ambas coinciden con el instante de congelar. En diferido, `[momento - 1440min, momento + 1440min]` en hora local de Madrid (research.md §6), aunque la consulta interna use UTC. |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='host_externo'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de host externo (`snapshot_evidencia`, JSON)

Todos los campos de orígenes anteriores se mantienen presentes con
valor `null`. Se añaden dos claves nuevas:

```json
{
  "...": "(resto de campos heredados a null)",
  "host_externo_actual": {
    "nombre": "Host de Uptime Kuma",
    "beszel_name": "UptimeKuma",
    "status": "sin_evidencia",
    "raw_status": null,
    "data_age_s": 1820.4,
    "hb_age_s": null
  },
  "host_externo_stats": null
}
```

o, en diferido:

```json
{
  "...": "(resto de campos heredados a null)",
  "host_externo_actual": null,
  "host_externo_stats": {
    "total_muestras": 0,
    "primera": null,
    "ultima": null,
    "por_tipo": {},
    "nombre": "Host de Uptime Kuma",
    "beszel_name": "UptimeKuma"
  }
}
```

`nombre`/`beszel_name` los añade `congelar_host_externo_historico()`
después de llamar a `_resumen_system_stats()` (que en sí misma es
agnóstica al host) — sin ellos, el modelo no tiene ninguna forma de
saber qué componente está diagnosticando, un fallo real encontrado en
la validación en vivo (T020, research.md §12): el primer diagnóstico
contra el episodio real de la avería del 30 de julio al 7 de agosto
concluyó "ni siquiera se puede determinar qué componente... estaba en
episodio" — la propia evidencia, tal como se envía a DeepSeek, no
llevaba el nombre del host en ningún sitio.

| Clave nueva | Presente cuando | Contenido |
|---|---|---|
| `host_externo_actual` | Episodio en vivo | `{nombre, beszel_name, status, raw_status, data_age_s, hb_age_s}` — `status` es `"arriba"`/`"caido"`/`"sin_evidencia"`, ya calculado con la misma política de frescura que `app.py` (research.md §3). `null` en diferido. |
| `host_externo_stats` | Episodio en diferido | Resumen de densidad de `system_stats` en la ventana (research.md §5) — `{beszel_name, total_muestras, primera, ultima, por_tipo}`. `total_muestras: 0` es ausencia de datos comprobada, **nunca** "caído confirmado" (FR-006a). `null` en vivo, **y también** en diferido si `nombre` no está en `HOSTS_EXTERNOS` o si la consulta al hub falló (Docker no disponible) — distinto de `total_muestras: 0`, que exige que la consulta haya tenido éxito de verdad (research.md §10). |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio.

## Esquema SQLite

**Sin cambios** respecto a `specs/013-.../data-model.md` — ninguna
migración nueva (research.md §1). El hub de Beszel tampoco cambia de
esquema — este feature solo lo consulta con `SELECT` parametrizado
(research.md §7).

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `HOSTS_EXTERNOS` | `{"Host de Uptime Kuma": "UptimeKuma", "Host de AdGuard Home (DNS primario)": "AdGuardHome"}` | Mapeo nombre canónico → nombre en Beszel (research.md §2). |
| `BESZEL_HOSTS_JSON` | `/Volumes/FastData/homelab/docker/homelab-orchestrator/data/beszel_hosts.json` (configurable) | Fuente de evidencia en vivo (research.md §3). |
| `BESZEL_HOSTS_HEARTBEAT` | `/Volumes/FastData/homelab/data/heartbeats/beszel-hosts.json` (configurable) | Segunda mitad de la política de frescura en vivo (research.md §3). |
| `BESZEL_HOSTS_MAX_AGE_S` | `900` | Mismo umbral exacto que `app.py::BESZEL_HOSTS_MAX_AGE_S` (research.md §3). |
| `BESZEL_HUB_VOLUME` | `"beszel_hub_data"` | Volumen Docker consultado en diferido (research.md §7). |
| `VENTANA_HOST_EXTERNO_MINUTOS` | `1440` (±24h) | Ventana alrededor del momento pedido en diferido — cubre 2-3 muestras `480m` esperadas en operación sana (research.md §6). |
