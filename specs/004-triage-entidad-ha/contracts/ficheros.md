# Contrato — Ficheros y semántica de este feature

**Feature**: [../spec.md](../spec.md)

Sin CLI ni API nueva. El contrato es la ampliación de un fichero que ya
existe y un nuevo valor en un enum ya cerrado.

## `ha_monitor_state.json` (ampliado, mismo productor)

**Productor**: `ha_monitor.py`, sin cambio de cadencia (cada 15 min).

**Consumidor nuevo**: `_homelab_bridge.py::ha_monitor_check_result()`,
usado por `evaluate.py` para las 65 entidades `entidad_ha` que están en
`CHECKS` (las 15 ya existentes + las 50 de este feature).

**Garantías**:

1. Las 50 claves nuevas siguen exactamente el mismo esquema
   `{ok, down_since, label, motivo, detail}` que las 15 existentes — sin
   campos nuevos a nivel de fichero.
2. Un check con `requires_container` que no puede ejecutarse porque el
   contenedor está parado se escribe como `ok=true, motivo=""` — nunca
   como una clave ausente ni como un valor de error fabricado
   (`data-model.md`).
3. `ha_monitor.py` sigue escribiendo el fichero entero en cada ciclo
   (no incremental) — sin cambio de ese comportamiento.

## `esta_vigilado` para `entidad_ha` (cambio de contrato interno)

**Antes**: `esta_vigilado` = ¿está el `entity_id` en
`ha_monitor.CHECKS`? (membresía, no resultado).

**Después**: `esta_vigilado` = ¿el último resultado real de ese check en
`ha_monitor_state.json` tiene `ok=true`? — aplicado a los 65 checks de
`entidad_ha` en `CHECKS`, no solo a los 50 nuevos (`research.md` §4).

**Consumidores afectados**: `evaluate.py::evaluate_component()` (todas
las llamadas para `categoria == "entidad_ha"`), y por extensión
`classify_gap()`/`gap_context()`, que ahora pueden devolver el tipo
nuevo `condicion_incumplida` para cualquiera de los 65, no solo los 50
de este feature.

**Riesgo evaluado y descartado**: que este cambio genere brechas nuevas
de golpe sobre los 15 checks existentes — comprobado en vivo el
2026-08-09, los 15 están en `ok=true`; el cambio de contrato no mueve
ningún número de la línea base existente.

## Tipo de brecha `condicion_incumplida` (nuevo valor de enum)

**Productor**: `evaluate.py::classify_gap()`.

**Consumidores**: `deliver.py` (JSON del dashboard, campo `tipo` de cada
brecha — ya es una cadena libre validada contra `TIPOS_BRECHA`, ningún
cambio de esquema ahí), `cli.py` (listado `--gaps`, ya imprime `tipo`
tal cual).

**Garantía**: el enum es cerrado (`model.py::TIPOS_BRECHA`) — cualquier
otro consumidor que valide contra esa tupla debe incluir el valor nuevo
o fallará explícitamente (`Brecha.__post_init__`), nunca en silencio.

## `requires_container` en `ha_monitor.CHECKS` como fuente de verdad de qué es "de Frigate" (hallazgo M1 de `/speckit-analyze`)

**Productor**: `ha_monitor.CHECKS`, campo `requires_container` en las 33
entradas de Frigate.

**Consumidor nuevo**: `_homelab_bridge.py::ha_monitor_conditional_entities()`,
usado por `sources.py::entidad_ha_frigate()`, usado por
`evaluate.py::is_intentional()`.

**Garantías**:

1. Mientras `ha_monitor.py` no tenga las 33 entradas con
   `requires_container` (antes de desplegar User Story 3),
   `ha_monitor_conditional_entities()` devuelve un conjunto vacío, y
   `entidad_ha_frigate()` cae a `_ENTIDAD_HA_FRIGATE_FALLBACK` (fijo, en
   este repo) — User Story 1 funciona igual de bien con o sin User
   Story 3 desplegada.
2. En cuanto `ha_monitor.py` tiene esas 33 entradas,
   `ha_monitor_conditional_entities()` deja de devolver un conjunto
   vacío, y **esa** lista manda — `_ENTIDAD_HA_FRIGATE_FALLBACK` deja de
   consultarse. Dos listas que puedan desincronizarse solo importa
   mientras la que manda esté vacía; en cuanto deja de estarlo, la otra
   es inerte por diseño, no por disciplina de mantenimiento.
3. `ha_monitor_conditional_entities()` nunca lanza — mismo contrato "a
   prueba de fallos" que el resto de `_homelab_bridge.py`.

## Fuera de este contrato

- El esquema de `ha_monitor.CHECKS` en sí (`id`, `label`, `type`,
  `entity`, `ok_state`/`threshold`/`requires_container` según el tipo) —
  es una dependencia de implementación de `ha_monitor.py`, no algo que
  este repo consuma directamente más allá de los campos `entity` y
  `requires_container` (ya leía `entity` desde feature 001).
- `docker/homelab-dashboard/scripts/app.py` — explícitamente sin cambios
  (`research.md` §5, `plan.md` Constraints).
