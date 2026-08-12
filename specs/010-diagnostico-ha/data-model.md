# Data Model — Generalizar el Diagnóstico a Home Assistant

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Generaliza el modelo ya existente de
`specs/007-diagnostico-episodios/data-model.md`, extendido por
`specs/009-diagnostico-discos/data-model.md` — no lo sustituye. Solo se
documentan aquí los campos que cambian de significado o de forma.

## Episodio (generalizado, sin cambio de esquema SQL)

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Sin cambios. |
| `origen` | TEXT | Tercer valor real: `"ha"` (además de `"contenedor"`/`"disco"`). **Sin migración** — la columna ya es TEXT libre desde 009 (research.md §1). |
| `componente` | TEXT | Para `origen='ha'`: el `check_id` de `ha_monitor.CHECKS` (`"bateria_interruptor_salon"`, `"ha_recorder_corrupto"`, `"ha_api"`, ...) — no el `entity_id` de Home Assistant (research.md §2). |
| `es_critico` | INTEGER (bool) | Para `origen='ha'`, siempre `False` (research.md §8) — no existe concepto de "check de HA crítico". |
| `en_vivo` | INTEGER (bool) | Sin cambios — `1` si viene de `--ha-vivo`. |
| `restart_history_id` | INTEGER, NULL | Sin cambios — `NULL` siempre para `origen='ha'`. |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Para checks de entidad: ventana real de 24h (12h ± momento) sobre el historial de HA (research.md §6). Para `recorder_corrupto`/`api_ping`: refleja el momento pedido, pero la evidencia en sí es del estado *actual* (limitación aceptada, research.md §6). |
| `snapshot_evidencia` | TEXT (JSON) | Forma nueva para `origen='ha'` — ver más abajo. |
| `creado_en` | TEXT (ISO 8601) | Sin cambios. |

### Forma del snapshot para un episodio de HA (`snapshot_evidencia`, JSON)

Los seis campos ya existentes (`disco`, `restart_history`,
`container_metrics`, `container_metrics_hourly`, `disk_metrics`,
`docker_inspect`) se mantienen presentes con valor `null` en un
episodio de HA — mismo criterio ya establecido en 007/009: un
consumidor del snapshot nunca comprueba si una clave existe, solo si es
`null`. Se añaden cuatro claves nuevas, y se reutiliza una ya existente:

```json
{
  "disco": null,
  "restart_history": null,
  "container_metrics": null,
  "container_metrics_hourly": null,
  "disk_metrics": null,
  "docker_inspect": null,
  "docker_logs_tail": null,
  "ha_check": {
    "id": "bateria_interruptor_salon",
    "type": "entity_value_below",
    "entity": "sensor.interruptor_salon_battery"
  },
  "ha_check_status": {"ok": true, "detalle": "OK", "motivo": ""},
  "ha_history": [
    {"state": "87", "last_changed": "..."}
  ],
  "ha_recorder_corrupt_files": null
}
```

| Clave nueva/reutilizada | Presente cuando | Contenido |
|---|---|---|
| `ha_check` | Siempre que `check_id` exista en `ha_monitor.CHECKS` (§3 de research.md); `null` si no existe | El dict del check tal cual lo declara `ha_monitor.CHECKS` (`id`, `type`, `entity`/`contenedor`/`ruta`/`ok_state`/`umbral` según el tipo) — le da a DeepSeek el "estado esperado declarado" del check (Principio III), no solo su resultado. |
| `ha_check_status` | Siempre que `ha_check` esté resuelto; `null` si no | **Añadido tras hallazgo real de validación en vivo (research.md §12)**. El veredicto ya calculado por `ha_monitor.check_status()` — `{"ok": bool, "detalle": str, "motivo": str}` — mismo cálculo que ese módulo ya hace cada 15 minutos. Le dice al modelo si *este check concreto* está fallando ahora mismo, sin que tenga que reconstruirlo de logs compartidos por otros 110 checks ni de aritmética de fechas. |
| `ha_history` | `ha_check.type` es uno de `entity_state`/`entity_available`/`entity_value_below`/`entity_age_below` | Lista de cambios de estado de `ha_check.entity` en la ventana (research.md §4/§6), acotada a `HA_HISTORIAL_MAX_ENTRADAS` (50, research.md §13) y simplificada a `state`/`last_changed` por entrada. `[]` si la API respondió pero sin cambios en la ventana; `null` si la API no respondió o el check no es de tipo entidad. |
| `ha_recorder_corrupt_files` | `ha_check.type == "recorder_corrupto"` | Lista de nombres de fichero `*.corrupt.*` presentes ahora mismo (research.md §6) — `[]` si no hay ninguno; `null` para cualquier otro tipo de check. |
| `docker_logs_tail` (reutilizada) | `ha_check.type` es `recorder_corrupto` o `api_ping` | Últimas 200 líneas de `docker logs homeassistant`, `stdout`+`stderr` combinados (research.md §4/§5/§11) — misma clave que ya usan los episodios de contenedor, mismo significado ("logs recientes del contenedor relevante"); `null` para checks de entidad y para disco. |

## Hipótesis / Diagnóstico / Gasto diario

Sin cambios de esquema — ya eran agnósticos al origen del episodio
(`diagnostico_id`/`episodio_id` son claves foráneas por `id`, no
dependen de si el episodio es de contenedor, disco o HA).

## Esquema SQLite

**Sin cambios respecto a `specs/009-.../data-model.md`** — ninguna
migración nueva (research.md §1). El esquema completo (`episodios`,
`diagnosticos`, `hipotesis`, `gasto_diario`) es el mismo que dejó 009.

## Constantes nuevas (`evidencia.py`)

| Constante | Valor | Uso |
|---|---|---|
| `VENTANA_HA_ENTIDAD_HORAS` | `12` | Ventana ± horas para historial de entidad, en vivo e histórico (research.md §6). |
| `CHECKS_HA_EXCLUIDOS_CERRADURA` | `{"cerradura_up", "bateria_cerradura", "bateria_critica_cerradura"}` | Bloqueo duro en `congelar_ha_vivo`/`congelar_ha_historico` (research.md §7, FR-010). |
| `_HA_API_CONTENEDOR` | `"homeassistant"` | Contenedor cuyos logs son la evidencia del check `ha_api` (research.md §5). |
