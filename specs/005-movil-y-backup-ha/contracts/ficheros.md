# Contrato — Ficheros y semántica de este feature

**Feature**: [../spec.md](../spec.md)

Sin CLI ni API nueva. El contrato es un tipo de check nuevo sobre un
mecanismo que ya existe (`ha_monitor.CHECKS`/`ha_monitor_state.json`,
feature 004) y una condición nueva en una función ya existente
(`is_intentional()`).

## `entity_age_below` — tipo de check nuevo

**Productor**: `ha_monitor.py::check_status()`.

**Consumidor**: `ha_monitor_state.json`, leído sin cambios por
`_homelab_bridge.py::ha_monitor_check_result()` (feature 004).

**Garantías**:

1. Un valor `unavailable` o `unknown` cuenta como fallo, igual que
   `entity_available` — nunca "sano" por ausencia de dato (Principio
   II).
2. Un valor que no se puede interpretar como fecha ISO 8601 cuenta
   como fallo con motivo propio, nunca como excepción no controlada
   que tumbe el resto de `ha_monitor.py`.
3. El umbral (`max_age_s`) es un campo del propio check, no una
   constante global — dos checks `entity_age_below` distintos en el
   futuro podrían tener umbrales distintos sin conflicto.

## `is_intentional()` — condición `platform: mobile_app`

**Productor**: `sources.py::ha_entity_components()` (sin cambios,
feature 001) — ya calcula `platform` en el `meta` de cada componente.

**Consumidor nuevo**: `evaluate.py::is_intentional()`.

**Garantía**: una entidad con `platform: mobile_app` cuenta como
intencionada con independencia de su `entity_category` o de si está
`disabled_by` — las tres condiciones de `is_intentional()` para
`entidad_ha` son independientes entre sí (basta con que una se cumpla).

## Fuera de este contrato

- Las otras 4 entidades de `platform: backup` (estado del
  administrador, próxima copia programada, evento, último intento) —
  `spec.md` acota este feature a una sola señal (Assumptions).
- `docker/homelab-dashboard/scripts/app.py` — sin cambios
  (`research.md` §4).
