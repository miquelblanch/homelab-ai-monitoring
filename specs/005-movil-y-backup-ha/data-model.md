# Data Model — Metadatos de Móvil Fuera de Alcance y Backup Propio de HA

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Este feature no introduce ninguna base de datos, fichero ni tipo de
brecha nuevo — amplía `is_intentional()` con una condición ya barata
(`platform`, ya disponible) y `ha_monitor.CHECKS`/`check_status()` con
un tipo de check nuevo.

## `is_intentional()` — condición nueva en `evaluate.py`

```python
if c.categoria == "entidad_ha":
    if raw.meta.get("disabled_by") is not None:
        return True
    if raw.meta.get("platform") == "mobile_app":  # feature 005
        return True
    if (
        raw.meta.get("entity_category") in ("config", "diagnostic")  # feature 004
        and c.nombre_actual not in ENTIDAD_HA_EXCEPCIONES_SEGURIDAD
        and c.nombre_actual not in entidad_ha_frigate()
    ):
        return True
    return False
```

Sin lectura nueva: `raw.meta["platform"]` ya lo calcula
`sources.py::ha_entity_components()` desde feature 001.

## `ha_monitor.CHECKS` — 1 entrada nueva, tipo `entity_age_below`

```python
{
    "id":         "ha_backup_reciente",
    "label":      "Backup automático de Home Assistant",
    "type":       "entity_age_below",
    "entity":     "sensor.backup_ultima_copia_de_seguridad_automatica_realizada_correctamente",
    "max_age_s":  129600,  # 36 h — "un día y medio", FR-004
}
```

## `check_status()` — tipo nuevo `entity_age_below`

Añade una rama al dispatcher existente, con el mismo contrato de
retorno `(ok, detalle, motivo)` que ya usan `entity_state`,
`entity_available` y `entity_value_below`:

1. Lee el `state` de la entidad (misma llamada `ha_get_detallado` que
   ya usan los otros tres tipos).
2. `state` en `("unavailable", "unknown")` → `(False, state,
   "no_disponible")` — mismo motivo que ya usa `entity_available`
   para el mismo caso (`research.md` de feature 004, ampliado aquí a
   `entity_age_below`).
3. `state` no interpretable como fecha ISO 8601 → `(False, "fecha no
   interpretable: <state>", "no_numerico")` — mismo motivo que ya usa
   `entity_value_below` para un valor no numérico; una fecha
   inválida es la misma clase de fallo de forma, no de contenido.
4. `state` interpretable → antigüedad en segundos =
   `datetime.now().timestamp() - fecha.timestamp()`. Si supera
   `check["max_age_s"]` → `(False, "última copia hace {h}h > umbral
   {h}h", "umbral")` — mismo motivo que ya usa `entity_value_below`
   para un valor bajo el umbral (aquí, un valor *sobre* el umbral).
   Si no → `(True, "hace {h}h", "")`.

## `ha_monitor_state.json` — sin cambio de esquema

La clave nueva (`ha_backup_reciente`) usa el mismo formato
`{ok, down_since, label, motivo, detail}` que las 66 ya existentes.

## Consumo desde este repo — sin cambios

`_vigilancia_entidad_ha()`, `classify_gap()` y `gap_context()`
(`evaluate.py`, feature 004) ya leen cualquier entrada de
`ha_monitor.CHECKS`/`ha_monitor_state.json` de forma genérica — el
check nuevo se clasifica como `sin_declaracion` mientras no exista,
`condicion_incumplida` si existe y `ok=false`, y deja de ser brecha si
`ok=true`, sin ningún cambio de código en este repo (`research.md`
§3).
