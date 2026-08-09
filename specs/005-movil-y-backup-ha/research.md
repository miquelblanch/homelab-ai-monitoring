# Research — Metadatos de Móvil Fuera de Alcance y Backup Propio de HA

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-08-09

Cada decisión se contrastó contra el código real —
`src/inventory/{evaluate,sources}.py`, `ha_monitor.py` — y contra el
registro y el estado en vivo de Home Assistant (2026-08-09).

## 1. Regla de `platform: mobile_app` (FR-001, FR-002)

**Decision**: `is_intentional()` en `evaluate.py`, rama `entidad_ha`,
gana una tercera condición junto a `disabled_by` y `entity_category`
(feature 004): `raw.meta.get("platform") == "mobile_app"` →
intencionado.

**Rationale**: `platform` ya viaja en el `meta` de cada componente
desde `sources.py::ha_entity_components()` (feature 001) — la misma
fuente que ya usa la regla de `entity_category`. Cero lectura nueva,
una condición más en una función que ya existe. Confirmado en vivo:
53 entidades con `platform: mobile_app` en las brechas actuales,
ninguna con `disabled_by` ni `entity_category` ya cubriéndola (no hay
solape con la regla de 004).

**Alternatives considered**: una lista fija de 53 `entity_id` — igual
que en 004, descartada: si Miquel añade un dispositivo nuevo con la
app móvil, sus entidades quedan cubiertas solas, sin tocar código
(Edge Cases de `spec.md`).

## 2. Backup propio de HA — qué comprobar y con qué tipo de check (FR-003, FR-004)

Investigado en vivo el 2026-08-09 contra el registro de HA
(`platform: backup`, 5 entidades) y sus valores reales:

- `sensor.backup_ultima_copia_de_seguridad_automatica_realizada_
  correctamente` — `device_class: timestamp`, valor
  `2026-08-09T03:04:33+00:00` en el momento de la investigación.
- `sensor.backup_proxima_copia_de_seguridad_automatica_programada` —
  próxima copia programada para el día siguiente ~02:51 UTC — confirma
  una cadencia diaria, mismo patrón que el resto de backups del
  homelab.
- `event.backup_copia_de_seguridad_automatica` — su último
  `event_type` era `completed` (no `failed`).

**Decision**: un único check nuevo sobre la primera entidad (la
antigüedad de la última copia correcta) — `spec.md` ya acota el alcance
a esa sola señal (Assumptions). Ninguno de los tipos de check
existentes en `ha_monitor.py` (`entity_state`, `entity_available`,
`entity_value_below`) comprueba la antigüedad de un valor — hace falta
un tipo nuevo, `entity_age_below`, que:
1. Lee el `state` de la entidad (una marca de tiempo ISO 8601).
2. Si es `unavailable`/`unknown` (nunca hubo copia, o dato no
   disponible), falla igual que `entity_available` — cubre el edge
   case de `spec.md` ("ausencia de dato no es lo mismo que una copia
   reciente").
3. Si no se puede interpretar como fecha, falla con un motivo propio
   (mismo patrón que `no_numerico` de `entity_value_below`, pero para
   fechas).
4. Si se puede interpretar, calcula la antigüedad en segundos
   (`datetime.now().timestamp() - fecha.timestamp()` — funciona igual
   con fechas con offset UTC explícito o sin él, sin necesitar manejar
   zonas horarias a mano) y la compara contra el umbral.

**Umbral**: 129600 s (36 h — "un día y medio", FR-004 de `spec.md`) —
mismo criterio que `verify_backups.py` (diario + margen), sin inventar
un número nuevo. La cadencia real observada (~24 h) deja margen de
sobra sin ser tan ancho como para tardar en avisar.

**Rationale**: mismo patrón de extensión que `requires_container` en
feature 004 — un tipo de check nuevo en el dispatcher `check_status()`,
reutilizando la estructura `(ok, detalle, motivo)` que ya usan los
otros tres tipos, sin tocar su forma.

**Alternatives considered**: cubrir también las otras 4 entidades de
`platform: backup` (estado del administrador, próxima copia programada,
evento, último intento) — descartado, `spec.md` ya lo acota
explícitamente a la señal mínima suficiente (Assumptions); las otras
4 quedan disponibles para un feature posterior sin que este tenga que
inventarles semántica ahora.

## 3. Por qué no hace falta tocar `evaluate.py` para la parte de vigilancia real (novedad frente a 004)

**Decision**: ningún cambio en `_vigilancia_entidad_ha()`,
`classify_gap()` ni `gap_context()`. El mecanismo que feature 004 ya
dejó construido —`esta_vigilado` lee el resultado real de
`ha_monitor_check_result()`, y `condicion_incumplida` es el tipo de
brecha cuando algo declarado incumple— se aplica automáticamente en
cuanto la nueva entrada exista en `ha_monitor.CHECKS`, sin código
adicional en este repo.

**Rationale**: es la prueba de que el diseño de 004 quedó
suficientemente general — un tipo de check nuevo (`entity_age_below`)
no necesita un tipo de brecha nuevo ni una función de evaluación nueva,
solo un productor de datos nuevo (`ha_monitor.py`) que ya habla el
mismo contrato (`{ok, down_since, label, motivo, detail}` en
`ha_monitor_state.json`).

## 4. Por qué este feature no toca `app.py` (igual que 004)

**Decision**: sin cambios en `docker/homelab-dashboard/scripts/app.py`
— mismo razonamiento que `research.md` §5 de feature 004: el recuento
"Domótica X/Y" ya suma todas las claves de `ha_monitor_state.json` sin
filtrar por listas fijas, así que el check nuevo ya mueve ese número en
cuanto existe.
